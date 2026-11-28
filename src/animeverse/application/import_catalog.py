"""Use case: import every configured franchise from a data source into the store.

For each franchise:
    1. search the source                        (AnimeSource: malformed results come back as rejections)
    2. keep only anime that belong to it         (the franchise's MembershipRule: removes search noise)
    3. save franchise, anime and links           (CatalogStore: ONE unit of work, all or nothing)
    4. reconcile its links                       (same unit of work: see below)

Failure handling:
- The source fails for a franchise, or its rule cannot decide membership
  (MembershipUndecidable): nothing is written for it, it is reported as
  failed, and the next franchise runs.
- The store refuses one anime: only that anime is skipped and reported;
  the rest of the franchise is still saved.
- The store fails as a whole during a franchise: that franchise is undone,
  reported as failed, and the next franchise runs.
- Any other exception is a bug and is NOT caught: it stops the import loudly.

Reconciliation (ADR 0012): after a successful search, a franchise keeps
only its current members. Every other anime is unlinked from it, and deleted
if that leaves it in no franchise and it is not in the watchlist. The
results we could not judge keep their links: anime the store refused and
malformed results with an id. A malformed result without an id could be
any anime, and relations that came incomplete could hide members, so in
either case the links are not reconciled at all (the report says why).

This module only knows the ports: it works the same with AniList and
PostgreSQL, or with the in-memory fakes used in the tests.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from animeverse.application.ports import (
    AnimeSource,
    CatalogStore,
    RecordRefused,
    Rejection,
    SearchResult,
    SourceUnavailable,
    StoreUnavailable,
    UnlinkedAnime,
)
from animeverse.domain.membership import FranchiseDefinition, MembershipUndecidable
from animeverse.domain.models import Anime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExcludedAnime:
    anilist_id: int
    title: str


@dataclass(frozen=True)
class UnsavedAnime:
    anilist_id: int
    title: str
    reason: str  # why the store refused it


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
    unlinked: list[UnlinkedAnime] = field(default_factory=list)  # no longer members (deleted or kept)
    reconciliation_skipped: str | None = None  # why the links were not reconciled, if they weren't


class ImportCatalog:
    def __init__(self, source: AnimeSource, store: CatalogStore) -> None:
        self._source = source
        self._store = store

    def run(self, franchises: Iterable[FranchiseDefinition]) -> list[FranchiseReport]:
        """Import every franchise. A failure in one never stops the others."""
        reports = []
        for definition in franchises:
            logger.info("Importing %s (search %r)", definition.name, definition.franchise.search_query)
            report = self.import_franchise(definition)
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

    def import_franchise(self, definition: FranchiseDefinition) -> FranchiseReport:
        report = FranchiseReport(definition.name)

        # 1. Search first, before opening a unit of work, so the store never waits on the network.
        try:
            result = self._source.search(definition.franchise.search_query)
        except SourceUnavailable as exc:
            return _fail(report, f"source: {exc}")
        report.fetched = result.fetched
        report.rejected = result.rejected

        # 2. Keep only the anime that belong to this franchise.
        try:
            members = definition.rule.select_members(result.anime, result.relations)
        except MembershipUndecidable as exc:
            return _fail(report, f"membership: {exc}")
        member_ids = {anime.anilist_id for anime in members}
        for anime in result.anime:
            if anime.anilist_id not in member_ids:
                report.excluded.append(ExcludedAnime(anime.anilist_id, anime.title))
                logger.info(
                    "%s: excluded %r (%d), not part of the franchise", definition.name, anime.title, anime.anilist_id
                )

        # 3. Save everything for this franchise in one unit of work.
        new = new_links = 0
        unsaved: list[UnsavedAnime] = []
        try:
            with self._store.session() as session:
                franchise_id = session.save_franchise(definition.franchise)
                for anime in members:
                    try:
                        saved = session.save_member(franchise_id, anime)
                    except RecordRefused as exc:
                        unsaved.append(UnsavedAnime(anime.anilist_id, anime.title, str(exc)))
                        logger.warning(
                            "%s: could not save %r (%d): %s", definition.name, anime.title, anime.anilist_id, exc
                        )
                        continue
                    new += saved.created
                    new_links += saved.newly_linked

                # 4. Reconcile: the franchise keeps only its current members.
                skip_reason = _reconciliation_blocker(result)
                if skip_reason is None:
                    unlinked = session.keep_only_links(franchise_id, _ids_to_keep(members, unsaved, result.rejected))
                    for gone in unlinked:
                        logger.info(
                            "%s: unlinked %r (%d), %s",
                            definition.name,
                            gone.title,
                            gone.anilist_id,
                            "deleted" if gone.deleted else "kept (in the watchlist or another franchise)",
                        )
                else:
                    unlinked = []
                    logger.warning("%s: links not reconciled: %s", definition.name, skip_reason)
        except StoreUnavailable as exc:
            return _fail(report, f"store: {exc}")

        report.unsaved = unsaved
        report.new = new
        report.refreshed = len(members) - len(unsaved) - new
        report.new_links = new_links
        report.unlinked = unlinked
        report.reconciliation_skipped = skip_reason
        return report


def _fail(report: FranchiseReport, error: str) -> FranchiseReport:
    report.failed = True
    report.error = error
    return report


def _reconciliation_blocker(result: SearchResult) -> str | None:
    """Why the links can't be reconciled safely, or None if they can.

    Unlinking needs a complete picture, or it could remove an anime that still belongs:
    - a malformed result without an id could be any anime;
    - a result with incomplete relations may connect anime the walk could not reach.
    """
    without_id = sum(r.source_id is None for r in result.rejected)
    if without_id:
        return f"{without_id} rejected result(s) without an id: can't tell which anime they were"
    if result.incomplete_relations:
        ids = ", ".join(str(i) for i in sorted(result.incomplete_relations))
        return f"incomplete relations for {len(result.incomplete_relations)} result(s) ({ids})"
    return None


def _ids_to_keep(members: list[Anime], unsaved: list[UnsavedAnime], rejected: list[Rejection]) -> frozenset[int]:
    """The members, plus the results we could not judge (refused or malformed): their links stay."""
    kept = {a.anilist_id for a in members} | {u.anilist_id for u in unsaved}
    kept |= {r.source_id for r in rejected if r.source_id is not None}
    return frozenset(kept)
