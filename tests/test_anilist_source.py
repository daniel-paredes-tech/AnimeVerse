"""Tests for AniListSource, the AnimeSource adapter. A fake AniList, no network."""

import httpx
import pytest

from animeverse.application.ports import SourceUnavailable
from animeverse.infrastructure.anilist.client import AniListClient
from animeverse.infrastructure.anilist.source import AniListSource


def source_answering(*responses: httpx.Response) -> AniListSource:
    queue = list(responses)
    http = httpx.Client(transport=httpx.MockTransport(lambda request: queue.pop(0)))
    client = AniListClient(http_client=http, sleep=lambda seconds: None, initial_requests_per_minute=600)
    return AniListSource(client)


def page(media: list) -> httpx.Response:
    return httpx.Response(200, json={"data": {"Page": {"pageInfo": {"hasNextPage": False}, "media": media}}})


def test_results_become_anime_and_rejections():
    source = source_answering(page([{"id": 900001, "title": {"romaji": "Test Anime"}}, {"id": None}]))

    result = source.search("test")

    assert [a.anilist_id for a in result.anime] == [900001]
    assert [r.position for r in result.rejected] == [1]
    assert result.fetched == 2


def test_anilist_failure_becomes_source_unavailable():
    source = source_answering(*[httpx.Response(503) for _ in range(4)])  # 1 attempt + 3 retries

    with pytest.raises(SourceUnavailable, match="AniList"):
        source.search("test")
