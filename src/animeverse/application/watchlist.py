"""Use case: manage the user's watchlist (create or replace an entry, remove it).

Saving an entry:
    1. find the anime                 (CatalogQuery)  missing -> AnimeNotFound
    2. tidy the entry                 blank notes become None
    3. check the domain rules         against the anime's episodes -> InvalidWatchlistEntry
    4. save it                        (WatchlistStore) create or replace

Steps 1 and 4 are separate store calls: if an import changed the anime's
episodes in between, the entry could be checked against the old number.
Imports are rare and never delete anime, so this is accepted (ADR 0011).
"""

from animeverse.application.errors import AnimeNotFound, InvalidWatchlistEntry, WatchlistEntryNotFound
from animeverse.application.ports import CatalogQuery, SavedEntry, WatchlistStore
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
        return self._store.save(anime_id, entry)

    def remove(self, anime_id: int) -> None:
        """Raises AnimeNotFound, WatchlistEntryNotFound or StoreUnavailable."""
        if self._catalog.get_anime(anime_id) is None:
            raise AnimeNotFound(anime_id)
        if not self._store.delete(anime_id):
            raise WatchlistEntryNotFound(anime_id)
