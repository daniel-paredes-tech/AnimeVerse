"""Use case: manage the user's watchlist (create or replace an entry, remove it).

Saving an entry:
    1. find the anime                 (CatalogQuery)  missing -> AnimeNotFound
    2. tidy the entry                 blank notes become None
    3. check the domain rules         against the anime's episodes -> InvalidWatchlistEntry
    4. save it                        (WatchlistStore) create or replace

Steps 1 and 4 are separate store calls: if an import changed the anime's
episodes in between, the entry could be checked against the old number.
Imports are rare, so this is accepted (ADR 0011). An import could also
delete the anime in between, if it stopped belonging to any franchise
(ADR 0012): the store then refuses the entry, and save reports AnimeNotFound.
"""

from animeverse.application.errors import AnimeNotFound, InvalidWatchlistEntry, WatchlistEntryNotFound
from animeverse.application.ports import CatalogQuery, RecordRefused, SavedEntry, WatchlistStore
from animeverse.domain.watchlist import WatchlistEntry, check_entry, without_blank_notes


class ManageWatchlist:
    def __init__(self, catalog: CatalogQuery, store: WatchlistStore) -> None:
        self._catalog = catalog
        self._store = store

    def save(self, anime_id: int, entry: WatchlistEntry) -> SavedEntry:
        """Create or replace the entry. Raises AnimeNotFound, InvalidWatchlistEntry or StoreUnavailable."""
        anime = self._catalog.get_anime(anime_id)
        if anime is None:
            raise AnimeNotFound(anime_id)
        entry = without_blank_notes(entry)
        violations = check_entry(entry, anime.anime.episodes)
        if violations:
            raise InvalidWatchlistEntry(violations)
        try:
            return self._store.save(anime_id, entry)
        except RecordRefused:
            # The domain rules passed, so the likely cause is that an import deleted
            # the anime since we read it (ADR 0012). If so, say so; otherwise it's a bug.
            if self._catalog.get_anime(anime_id) is None:
                raise AnimeNotFound(anime_id) from None
            raise

    def remove(self, anime_id: int) -> None:
        """Raises AnimeNotFound, WatchlistEntryNotFound or StoreUnavailable."""
        if self._catalog.get_anime(anime_id) is None:
            raise AnimeNotFound(anime_id)
        if not self._store.delete(anime_id):
            raise WatchlistEntryNotFound(anime_id)
