"""Use case: import every configured franchise from a data source into the store.

For each franchise:
    1. search the source                        (AnimeSource: malformed results come back as rejections)
    2. keep only anime that belong to it         (the franchise's MembershipRule: removes search noise)
    3. save franchise, anime and links           (CatalogStore: ONE unit of work, all or nothing)

Failure handling:
- The source fails for a franchise: nothing is written for it, it is
  reported as failed, and the next franchise runs.
- The store refuses one anime: only that anime is skipped and reported;
  the rest of the franchise is still saved.
- The store fails as a whole during a franchise: that franchise is undone,
  reported as failed, and the next franchise runs.
- Any other exception is a bug and is NOT caught: it stops the import loudly.

Imports only insert and refresh. An anime that disappears from the source
is never deleted.

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
    SourceUnavailable,
    StoreUnavailable,
)
from animeverse.domain.membership import FranchiseDefinition

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
        members = []
        for anime in result.anime:
            if definition.rule.includes(anime):
                members.append(anime)
            else:
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
        except StoreUnavailable as exc:
            return _fail(report, f"store: {exc}")

        report.unsaved = unsaved
        report.new = new
        report.refreshed = len(members) - len(unsaved) - new
        report.new_links = new_links
        return report


def _fail(report: FranchiseReport, error: str) -> FranchiseReport:
    report.failed = True
    report.error = error
    return report
