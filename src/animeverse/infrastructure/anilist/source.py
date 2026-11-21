"""AniListSource: the AnimeSource port, implemented with the AniList API.

It joins the two AniList pieces: the client fetches raw results, the mapper
turns them into Anime models. AniList's own error type never leaves this
module: it becomes the port's SourceUnavailable.
"""

from animeverse.application.ports import SearchResult, SourceUnavailable
from animeverse.infrastructure.anilist.client import AniListClient, AniListError
from animeverse.infrastructure.anilist.mapper import parse_anime_list


class AniListSource:
    def __init__(self, client: AniListClient) -> None:
        self._client = client

    def search(self, query: str) -> SearchResult:
        try:
            raw_items = self._client.search_anime(query)
        except AniListError as exc:
            raise SourceUnavailable(f"AniList: {exc}") from exc
        return parse_anime_list(raw_items)
