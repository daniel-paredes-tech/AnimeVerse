"""Tests for animeverse.anilist_client.

All tests except the one marked "live" use a fake AniList (httpx.MockTransport)
and a fake clock, so they need no network and never really wait.
The media items below are made-up test data.
"""

import json

import httpx
import pytest

from animeverse.anilist_client import API_URL, PER_PAGE, AniListClient, AniListError


class FakeTime:
    """A virtual clock: sleep() records the wait and moves time forward instantly."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


class FakeAniList:
    """Returns the given responses in order and records every request it receives."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def page(media, has_next=False, headers=None, status=200):
    """A response shaped like AniList's Page query result."""
    body = {"data": {"Page": {"pageInfo": {"hasNextPage": has_next}, "media": media}}}
    return httpx.Response(status, json=body, headers=headers)


def error(status, message, headers=None):
    """A response shaped like AniList's documented error format."""
    body = {"errors": [{"message": message, "status": status}], "data": None}
    return httpx.Response(status, json=body, headers=headers)


@pytest.fixture
def fake_time():
    return FakeTime()


@pytest.fixture
def make_client(fake_time):
    # A high initial rate keeps pacing (0.1 s) out of the way in tests that
    # check retry waits; the pacing tests set the rate via response headers.
    def _make(fake_anilist, **kwargs):
        kwargs.setdefault("initial_requests_per_minute", 600)
        http = httpx.Client(transport=httpx.MockTransport(fake_anilist))
        return AniListClient(http_client=http, sleep=fake_time.sleep, clock=fake_time.clock, **kwargs)

    return _make


def sent_variables(request: httpx.Request) -> dict:
    return json.loads(request.content)["variables"]


# --- Successful responses ---------------------------------------------------


def test_search_page_returns_media_and_has_next_page(make_client):
    fake = FakeAniList(page([{"id": 1}, {"id": 2}], has_next=True))

    result = make_client(fake).search_anime_page("naruto", 1)

    assert result.media == [{"id": 1}, {"id": 2}]
    assert result.has_next_page is True


def test_request_sends_query_variables_and_headers(make_client):
    fake = FakeAniList(page([]))

    make_client(fake).search_anime_page("naruto", 2)

    request = fake.requests[0]
    body = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == API_URL
    assert request.headers["Accept"] == "application/json"
    assert body["variables"] == {"search": "naruto", "page": 2}
    # The search text travels as a variable, never inside the query string.
    assert "naruto" not in body["query"]
    assert f"perPage: {PER_PAGE}" in body["query"]


def test_search_anime_follows_pages_until_has_next_page_is_false(make_client):
    fake = FakeAniList(
        page([{"id": 1}], has_next=True),
        page([{"id": 2}], has_next=True),
        page([{"id": 3}], has_next=False),
    )

    media = make_client(fake).search_anime("naruto")

    assert media == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert [sent_variables(r)["page"] for r in fake.requests] == [1, 2, 3]


def test_search_anime_raises_when_page_cap_is_exceeded(make_client):
    fake = FakeAniList(*[page([{"id": n}], has_next=True) for n in range(5)])

    with pytest.raises(AniListError, match="after 2 pages"):
        make_client(fake).search_anime("naruto", max_pages=2)

    assert len(fake.requests) == 2  # stopped at the cap, didn't keep going


# --- Temporary failures are retried -----------------------------------------


def test_server_error_is_retried_then_succeeds(make_client, fake_time):
    fake = FakeAniList(error(500, "Internal Server Error"), page([{"id": 1}]))

    result = make_client(fake).search_anime_page("naruto", 1)

    assert result.media == [{"id": 1}]
    assert fake_time.sleeps == [1.0]


def test_timeout_is_retried_then_succeeds(make_client, fake_time):
    fake = FakeAniList(httpx.ReadTimeout("timed out"), page([{"id": 1}]))

    result = make_client(fake).search_anime_page("naruto", 1)

    assert result.media == [{"id": 1}]
    assert fake_time.sleeps == [1.0]


def test_persistent_server_error_gives_up_after_three_retries(make_client, fake_time):
    fake = FakeAniList(*[error(503, "Service Unavailable") for _ in range(4)])

    with pytest.raises(AniListError, match="after 4 attempts") as caught:
        make_client(fake).search_anime_page("naruto", 1)

    assert caught.value.status == 503
    assert len(fake.requests) == 4  # 1 attempt + 3 retries
    assert fake_time.sleeps == [1.0, 2.0, 4.0]  # exponential backoff


def test_rate_limited_request_waits_retry_after(make_client, fake_time):
    fake = FakeAniList(error(429, "Too Many Requests.", headers={"Retry-After": "7"}), page([]))

    make_client(fake).search_anime_page("naruto", 1)

    assert fake_time.sleeps == [7.0]


def test_rate_limited_without_retry_after_waits_sixty_seconds(make_client, fake_time):
    fake = FakeAniList(error(429, "Too Many Requests."), page([]))

    make_client(fake).search_anime_page("naruto", 1)

    assert fake_time.sleeps == [60.0]


def test_rate_limited_with_a_huge_retry_after_fails_instead_of_waiting(make_client, fake_time):
    fake = FakeAniList(error(429, "Too Many Requests.", headers={"Retry-After": "86400"}), page([]))

    with pytest.raises(AniListError) as caught:
        make_client(fake).search_anime_page("naruto", 1)

    assert caught.value.status == 429
    assert len(fake.requests) == 1  # no retry
    assert fake_time.sleeps == []  # and no day-long sleep


# --- Permanent failures are raised immediately ------------------------------


@pytest.mark.parametrize(
    ("status", "message"),
    [(400, 'Cannot query field "x" on type "Media".'), (404, "Not Found.")],
)
def test_client_errors_are_not_retried(make_client, fake_time, status, message):
    fake = FakeAniList(error(status, message))

    with pytest.raises(AniListError, match=message) as caught:
        make_client(fake).search_anime_page("naruto", 1)

    assert caught.value.status == status
    assert len(fake.requests) == 1
    assert fake_time.sleeps == []


def test_graphql_errors_in_a_200_response_raise(make_client):
    body = {"errors": [{"message": "Something went wrong"}], "data": {"Page": None}}
    fake = FakeAniList(httpx.Response(200, json=body))

    with pytest.raises(AniListError, match="Something went wrong"):
        make_client(fake).search_anime_page("naruto", 1)


def test_non_json_response_raises(make_client):
    fake = FakeAniList(httpx.Response(200, text="<html>Maintenance</html>"))

    with pytest.raises(AniListError, match="non-JSON"):
        make_client(fake).search_anime_page("naruto", 1)


def test_unexpected_envelope_raises(make_client):
    fake = FakeAniList(httpx.Response(200, json={"data": {"Page": {"media": "not a list"}}}))

    with pytest.raises(AniListError, match="unexpected shape"):
        make_client(fake).search_anime_page("naruto", 1)


# --- Rate-limit pacing ------------------------------------------------------


@pytest.mark.parametrize(("limit", "expected_gap"), [("30", 2.0), ("90", 0.667)])
def test_requests_are_spaced_by_the_rate_limit_header(make_client, fake_time, limit, expected_gap):
    headers = {"X-RateLimit-Limit": limit}
    fake = FakeAniList(page([], headers=headers), page([], headers=headers))
    client = make_client(fake)

    client.search_anime_page("naruto", 1)
    client.search_anime_page("naruto", 2)

    # No wait before the first request; then 60 / limit seconds.
    assert fake_time.sleeps == [expected_gap]


# --- Live check against the real AniList (opt-in: pytest -m live) -----------

EXPECTED_MEDIA_FIELDS = {
    "id", "idMal", "title", "format", "episodes", "status", "startDate", "endDate",
    "weightedScore", "popularity", "description", "coverImage", "siteUrl",
}


@pytest.mark.live
def test_live_search_returns_every_queried_field():
    """Catches AniList renaming or removing a field our query depends on."""
    with AniListClient() as client:
        result = client.search_anime_page("naruto", 1)

    assert result.media, "AniList returned no results for 'naruto'"
    assert set(result.media[0]) == EXPECTED_MEDIA_FIELDS
