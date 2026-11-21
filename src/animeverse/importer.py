"""Import service: connects the client, parser and repository for each franchise.

For each franchise:
    1. fetch raw search results from AniList   (client)
    2. turn them into Anime models              (parser: malformed items are rejected)
    3. keep only anime that belong to it        (the franchise's MembershipRule: removes search noise)
    4. save franchise, anime and links          (repository: ONE transaction, all or nothing)

Failure handling:
- AniList fails for a franchise (after the client's retries): nothing is
  written for it, it is reported as failed, and the next franchise runs.
- PostgreSQL refuses one anime (a value it cannot store, a broken constraint):
  only that anime is undone, using a savepoint; it is reported as not saved
  and the rest of the franchise is still imported.
- Any other database error during a franchise (e.g. the connection drops):
  ROLLBACK, so that franchise is left exactly as it was; reported as failed;
  the next franchise runs.
- Any other exception is a bug in our code and is NOT caught: it stops the
  import loudly (the open transaction is rolled back when the connection closes).

Imports only insert and refresh. An anime that disappears from AniList's
results is never deleted.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

import psycopg

from animeverse.application.ports import Rejection
from animeverse.config.franchises import FRANCHISES
from animeverse.domain.membership import FranchiseDefinition
from animeverse.domain.models import Anime
from animeverse.infrastructure.anilist.client import AniListClient, AniListError
from animeverse.infrastructure.anilist.mapper import parse_anime_list
from animeverse.infrastructure.postgres import repository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExcludedAnime:
    anilist_id: int
    title: str


@dataclass(frozen=True)
class UnsavedAnime:
    anilist_id: int
    title: str
    reason: str  # PostgreSQL's error message


@dataclass
class FranchiseReport:
    name: str
    failed: bool = False
    error: str | None = None
    fetched: int = 0
    rejected: list[Rejection] = field(default_factory=list)
    excluded: list[ExcludedAnime] = field(default_factory=list)
    unsaved: list[UnsavedAnime] = field(default_factory=list)
    new: int = 0
    refreshed: int = 0
    new_links: int = 0


# --- Importing ---------------------------------------------------------------------


def import_franchise(
    client: AniListClient, conn: psycopg.Connection, definition: FranchiseDefinition
) -> FranchiseReport:
    report = FranchiseReport(definition.name)

    # 1. Fetch first, before any transaction, so the database never waits on the network.
    try:
        raw_items = client.search_anime(definition.franchise.search_query)
    except AniListError as exc:
        return _fail(report, f"AniList: {exc}")
    report.fetched = len(raw_items)

    # 2. Parse: malformed items are collected as rejections (and logged by the parser).
    parsed = parse_anime_list(raw_items)
    report.rejected = parsed.rejected

    # 3. Keep only the anime that belong to this franchise.
    members: list[Anime] = []
    for anime in parsed.anime:
        if definition.rule.includes(anime):
            members.append(anime)
        else:
            report.excluded.append(ExcludedAnime(anime.anilist_id, anime.title))
            logger.info(
                "%s: excluded %r (%d), not part of the franchise", definition.name, anime.title, anime.anilist_id
            )

    # 4. Save everything for this franchise in one transaction.
    try:
        franchise_id = repository.upsert_franchise(conn, definition.franchise)
        new = new_links = 0
        for anime in members:
            try:
                # A savepoint: if PostgreSQL refuses this anime, only this anime
                # is undone and the transaction stays usable for the others.
                with conn.transaction():
                    saved = repository.upsert_anime(conn, anime)
                    is_new_link = repository.link_anime_to_franchise(conn, saved.id, franchise_id)
            except (psycopg.DataError, psycopg.IntegrityError) as exc:
                reason = str(exc).splitlines()[0]
                report.unsaved.append(UnsavedAnime(anime.anilist_id, anime.title, reason))
                logger.warning("%s: could not save %r (%d): %s", definition.name, anime.title, anime.anilist_id, reason)
                continue
            new += saved.created
            new_links += is_new_link
        conn.commit()
    except psycopg.Error as exc:
        conn.rollback()
        return _fail(report, f"database: {exc}")

    report.new = new
    report.refreshed = len(members) - len(report.unsaved) - new
    report.new_links = new_links
    return report


def import_all(
    client: AniListClient,
    conn: psycopg.Connection,
    franchises: Iterable[FranchiseDefinition] = FRANCHISES,
) -> list[FranchiseReport]:
    """Import every franchise. A failure in one never stops the others."""
    reports = []
    for definition in franchises:
        logger.info("Importing %s (search %r)", definition.name, definition.franchise.search_query)
        report = import_franchise(client, conn, definition)
        if report.failed:
            logger.error("%s failed: %s", definition.name, report.error)
        else:
            logger.info(
                "%s: %d new, %d refreshed, %d excluded, %d rejected, %d not saved",
                definition.name,
                report.new,
                report.refreshed,
                len(report.excluded),
                len(report.rejected),
                len(report.unsaved),
            )
        reports.append(report)
    return reports


def _fail(report: FranchiseReport, error: str) -> FranchiseReport:
    report.failed = True
    report.error = error
    return report


# --- Report --------------------------------------------------------------------------


def format_report(reports: list[FranchiseReport]) -> str:
    """A plain-text summary of an import run."""
    header = (
        f"{'Franchise':<18}{'Status':<8}{'Fetched':>8}{'Rejected':>10}{'Excluded':>10}"
        f"{'New':>6}{'Refreshed':>11}{'New links':>11}"
    )
    lines = [header, "-" * len(header)]
    for r in reports:
        status = "FAILED" if r.failed else "ok"
        lines.append(
            f"{r.name:<18}{status:<8}{r.fetched:>8}{len(r.rejected):>10}{len(r.excluded):>10}"
            f"{r.new:>6}{r.refreshed:>11}{r.new_links:>11}"
        )

    excluded = [f"{r.name}: {e.title} ({e.anilist_id})" for r in reports for e in r.excluded]
    rejected = [f"{r.name}: position {x.position} (id={x.source_id}): {x.reason}" for r in reports for x in r.rejected]
    unsaved = [f"{r.name}: {u.title} ({u.anilist_id}): {u.reason}" for r in reports for u in r.unsaved]
    failures = [f"{r.name}: {r.error}" for r in reports if r.failed]
    for title, items in (
        ("Excluded (not part of the franchise)", excluded),
        ("Rejected (malformed data)", rejected),
        ("Not saved (refused by the database)", unsaved),
        ("Failures", failures),
    ):
        if items:
            lines += ["", f"{title}:"] + [f"  - {item}" for item in items]

    succeeded = sum(not r.failed for r in reports)
    lines += ["", f"Result: {succeeded} of {len(reports)} franchises imported."]
    return "\n".join(lines)
