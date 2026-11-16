"""Client for the AniList GraphQL API.

Responsibility: get data from AniList reliably (timeouts, retries, rate
limits, pagination). It does NOT interpret anime data: it returns the raw
media dictionaries exactly as AniList sent them, and the parser validates and
converts them. The client only checks the response envelope.

Verified AniList behaviour this client relies on (see CLAUDE.md section 5):
- Errors come with real HTTP status codes and a body like
  {"errors": [{"message": ..., "status": ...}], "data": ...}.
- 429 responses include Retry-After (seconds), followed by a 1-minute timeout.
- X-RateLimit-Limit reports the current requests-per-minute limit.
- perPage is silently capped at 50.
- Only pageInfo.hasNextPage is reliable for pagination.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://graphql.anilist.co"
# AniList silently reduces larger values to 50, so asking for more is pointless.
PER_PAGE = 50
# Generous compared with the ~0.2 s responses we measured, short enough not to hang an import.
TIMEOUT_SECONDS = 10.0
# Pacing assumption until a response tells us the real limit (degraded limit at time of writing).
DEFAULT_REQUESTS_PER_MINUTE = 30
# AniList documents a 1-minute timeout after a 429; used if Retry-After is missing or invalid.
DEFAULT_RETRY_AFTER_SECONDS = 60.0
# Temporary server-side failures worth retrying. 4xx errors are never retried.
RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})

HEADERS = {
    "Accept": "application/json",
    # Generic identification only: no personal or project-owner details.
    "User-Agent": "AnimeVerse/0.1 (educational project)",
}

# Only the fields approved for storage. The search text and page number are
# GraphQL variables, never pasted into the query string.
SEARCH_ANIME_QUERY = f"""
query ($search: String, $page: Int) {{
  Page(page: $page, perPage: {PER_PAGE}) {{
    pageInfo {{ hasNextPage }}
    media(search: $search, type: ANIME) {{
      id
      idMal
      title {{ romaji english native }}
      format
      episodes
      status
      startDate {{ year month day }}
      endDate {{ year month day }}
      weightedScore
      popularity
      description(asHtml: false)
      coverImage {{ large }}
      siteUrl
    }}
  }}
}}
"""


class AniListError(Exception):
    """A failure the client cannot or should not recover from."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status  # HTTP status code, when there was a response


@dataclass(frozen=True)
class AnimePage:
    """One page of search results: raw, unvalidated media dicts."""

    media: list[dict[str, Any]]
    has_next_page: bool


class AniListClient:
    def __init__(
        self,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        initial_requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        # Tests pass a fake http_client, sleep and clock, so no real network
        # or real waiting is involved.
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._max_retries = max_retries
        self._min_interval = 60.0 / initial_requests_per_minute
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None

    # --- Public interface ------------------------------------------------------

    def search_anime(self, search: str, max_pages: int = 10) -> list[dict[str, Any]]:
        """Return all raw media dicts for a search, following hasNextPage.

        Raises AniListError if there are still more pages after max_pages:
        a franchise that large means something is wrong (a too-broad search,
        or hasNextPage stuck on true), and a partial result must not be
        imported silently.
        """
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")

        results: list[dict[str, Any]] = []
        page = 1
        while True:
            result = self.search_anime_page(search, page)
            results.extend(result.media)
            if not result.has_next_page:
                return results
            if page >= max_pages:
                raise AniListError(
                    f"Search {search!r} still has more results after {max_pages} pages "
                    f"({len(results)} anime). Refusing to return a partial result."
                )
            page += 1

    def search_anime_page(self, search: str, page: int) -> AnimePage:
        """Fetch one page (up to PER_PAGE anime) of search results."""
        if not search.strip():
            raise ValueError("search must not be empty")
        if page < 1:
            raise ValueError("page must be at least 1")

        data = self._post({"query": SEARCH_ANIME_QUERY, "variables": {"search": search, "page": page}})

        # Check only the envelope; the media items themselves are the parser's job.
        page_data = data.get("Page")
        media = page_data.get("media") if isinstance(page_data, dict) else None
        page_info = page_data.get("pageInfo") if isinstance(page_data, dict) else None
        has_next = page_info.get("hasNextPage") if isinstance(page_info, dict) else None
        if not isinstance(media, list) or not isinstance(has_next, bool):
            raise AniListError(
                "AniList response has an unexpected shape: expected data.Page.media (list) "
                "and data.Page.pageInfo.hasNextPage (boolean)."
            )
        return AnimePage(media=media, has_next_page=has_next)

    def close(self) -> None:
        """Close the HTTP connection pool, if this client created it."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "AniListClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- One HTTP request, with pacing and retries ------------------------------

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send one GraphQL request and return its "data" object.

        Retries network errors, timeouts and 5xx responses with exponential
        backoff (1 s, 2 s, 4 s), and 429 responses after Retry-After.
        Everything else is returned or raised immediately.
        """
        retries_done = 0
        wait = 0.0
        while True:
            self._wait_before_request(wait)
            self._last_request_at = self._clock()
            try:
                response = self._http.post(API_URL, json=payload, headers=HEADERS)
            except httpx.TransportError as exc:  # includes timeouts and connection errors
                problem, status = f"network error ({type(exc).__name__}: {exc})", None
                wait = 2.0**retries_done
            else:
                self._update_rate_limit(response)
                status = response.status_code
                if status == 429:
                    problem = "rate limit reached (HTTP 429)"
                    wait = self._retry_after(response)
                elif status in RETRYABLE_STATUS_CODES:
                    problem = f"server error (HTTP {status})"
                    wait = 2.0**retries_done
                else:
                    return self._read_data(response)

            if retries_done >= self._max_retries:
                raise AniListError(
                    f"AniList request failed after {retries_done + 1} attempts: {problem}",
                    status=status,
                )
            retries_done += 1
            logger.warning(
                "AniList %s; retrying in %.1f s (retry %d of %d)",
                problem, wait, retries_done, self._max_retries,
            )

    def _wait_before_request(self, minimum_wait: float) -> None:
        """Sleep once, long enough for both the retry wait and the rate-limit pacing."""
        now = self._clock()
        earliest = now + minimum_wait
        if self._last_request_at is not None:
            earliest = max(earliest, self._last_request_at + self._min_interval)
        if earliest > now:
            self._sleep(earliest - now)

    def _update_rate_limit(self, response: httpx.Response) -> None:
        """Space requests by 60 / X-RateLimit-Limit seconds, when the header is valid."""
        try:
            limit = int(response.headers.get("X-RateLimit-Limit", ""))
        except ValueError:
            return  # missing or invalid: keep the current pacing
        if limit > 0:
            self._min_interval = 60.0 / limit

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        try:
            seconds = float(response.headers.get("Retry-After", ""))
        except ValueError:
            return DEFAULT_RETRY_AFTER_SECONDS
        return seconds if seconds >= 0 else DEFAULT_RETRY_AFTER_SECONDS

    @staticmethod
    def _read_data(response: httpx.Response) -> dict[str, Any]:
        """Return the "data" object of a final (non-retried) response, or raise."""
        status = response.status_code
        try:
            body = response.json()
        except ValueError:
            raise AniListError(f"AniList returned a non-JSON response (HTTP {status})", status) from None
        if not isinstance(body, dict):
            raise AniListError(f"AniList returned an unexpected JSON value (HTTP {status})", status)

        errors = body.get("errors")
        if errors:
            # Treat the error list as untrusted too: it may not have the documented shape.
            items = errors if isinstance(errors, list) else [errors]
            messages = "; ".join(
                str(item.get("message", item)) if isinstance(item, dict) else str(item) for item in items
            )
            raise AniListError(f"AniList returned an error (HTTP {status}): {messages}", status)

        if status != 200:
            raise AniListError(f"Unexpected HTTP {status} from AniList", status)

        data = body.get("data")
        if not isinstance(data, dict):
            raise AniListError("AniList response has no 'data' object", status)
        return data
