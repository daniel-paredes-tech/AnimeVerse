"""Mapper: turns raw AniList media dicts into validated Anime models.

The mapper is the gatekeeper for untrusted API data. Everything after it
(the repository, the database) can rely on clean, correctly typed values.

Policy:
- A missing or invalid REQUIRED field (id, title.romaji) rejects the item.
- An invalid OPTIONAL field becomes None (NULL) and a warning is logged.
  A merely missing optional value is normal and logged as nothing.
- Dates: AniList sends {year, month, day} and any part may be missing. A full
  date becomes a date; a partial one is not guessed, but its year is kept.
- parse_anime_list never raises for a bad item: one malformed record must
  not stop the rest of the import.
- Relations (the ids of related media) are kept apart from the Anime, in
  SearchResult.relations: they decide franchise membership and are never
  stored. A malformed relation is skipped with a warning.
"""

import html
import logging
import math
import re
from datetime import date
from decimal import Decimal
from typing import Any, TypeGuard
from urllib.parse import urlsplit

from animeverse.application.ports import Rejection, SearchResult
from animeverse.domain.models import Anime

logger = logging.getLogger(__name__)

# Largest value of a PostgreSQL INTEGER column. A bigger number would make the
# INSERT fail, so the parser refuses it here instead.
MAX_INTEGER = 2_147_483_647


class InvalidAnimeError(Exception):
    """Raised when an item cannot become an Anime (a required field is bad)."""


# --- Public interface ----------------------------------------------------------


def parse_anime_list(raw_items: list[Any]) -> SearchResult:
    """Parse many items. Bad items are collected as rejections, never raised."""
    valid: list[Anime] = []
    rejected: list[Rejection] = []
    relations: dict[int, frozenset[int]] = {}
    for position, raw in enumerate(raw_items):
        try:
            anime = parse_anime(raw)
        except InvalidAnimeError as exc:
            raw_id = raw.get("id") if isinstance(raw, dict) else None
            anilist_id = raw_id if _is_whole_number(raw_id) else None
            rejected.append(Rejection(position, anilist_id, str(exc)))
            logger.warning("Rejected AniList item at position %d (id=%s): %s", position, anilist_id, exc)
            continue
        valid.append(anime)
        relations[anime.anilist_id] = parse_relations(raw, anime.anilist_id)
    return SearchResult(anime=valid, rejected=rejected, relations=relations)


def parse_relations(raw: dict[str, Any], anilist_id: int) -> frozenset[int]:
    """The ids of the media an item relates to. Never raises.

    Missing or null relations are empty. A malformed edge is skipped with a
    warning; the other edges, and the anime itself, are kept.
    """
    relations = raw.get("relations")
    if relations is None:
        return frozenset()
    edges = relations.get("edges") if isinstance(relations, dict) else None
    if not isinstance(edges, list):
        logger.warning("AniList id %d: 'relations.edges' is not a list, got %s", anilist_id, _short(edges))
        return frozenset()

    related: set[int] = set()
    for edge in edges:
        node = edge.get("node") if isinstance(edge, dict) else None
        node_id = node.get("id") if isinstance(node, dict) else None
        if _is_whole_number(node_id) and 0 < node_id <= MAX_INTEGER:
            related.add(node_id)
        else:
            logger.warning("AniList id %d: skipped a malformed relation: %s", anilist_id, _short(edge))

    page_info = relations.get("pageInfo")
    if isinstance(page_info, dict) and page_info.get("hasNextPage") is True:
        # Not seen on 2026-11-28: the search returns every relation on one page.
        logger.warning("AniList id %d: has more relations than one page; only the first page is used", anilist_id)
    return frozenset(related)


def parse_anime(raw: Any) -> Anime:
    """Parse one AniList media dict. Raises InvalidAnimeError if a required field is bad."""
    if not isinstance(raw, dict):
        raise InvalidAnimeError(f"expected an object, got {type(raw).__name__}")

    # Required fields: without them we can neither identify nor display the anime.
    anilist_id = raw.get("id")
    if not _is_whole_number(anilist_id) or not 0 < anilist_id <= MAX_INTEGER:
        raise InvalidAnimeError(f"'id' must be a whole number from 1 to {MAX_INTEGER}, got {_short(anilist_id)}")
    titles = raw.get("title")
    if not isinstance(titles, dict):
        raise InvalidAnimeError(f"'title' must be an object, got {type(titles).__name__}")
    title = titles.get("romaji")
    if not isinstance(title, str) or not _clean_text(title):
        raise InvalidAnimeError(f"'title.romaji' must be non-empty text, got {_short(title)}")

    # Optional fields: invalid values become None with a warning.
    f = _OptionalFields(anilist_id)
    aired_from = f.date(raw.get("startDate"), "startDate")
    aired_to = f.date(raw.get("endDate"), "endDate")
    start_year = f.year(raw.get("startDate"), "startDate")
    end_year = f.year(raw.get("endDate"), "endDate")
    ends_before_start = (aired_from and aired_to and aired_to < aired_from) or (
        start_year and end_year and end_year < start_year
    )
    if ends_before_start:
        f.warn("endDate", raw.get("endDate"), "is before startDate")
        aired_to = end_year = None

    return Anime(
        anilist_id=anilist_id,
        title=_clean_text(title),
        mal_id=f.whole_number(raw.get("idMal"), "idMal", minimum=1),
        title_english=f.text(titles.get("english"), "title.english"),
        title_japanese=f.text(titles.get("native"), "title.native"),
        type=f.text(raw.get("format"), "format"),
        episodes=f.whole_number(raw.get("episodes"), "episodes", minimum=0),
        status=f.text(raw.get("status"), "status"),
        aired_from=aired_from,
        aired_to=aired_to,
        score=f.score(raw.get("weightedScore"), "weightedScore"),
        popularity=f.whole_number(raw.get("popularity"), "popularity", minimum=0),
        synopsis=f.synopsis(raw.get("description"), "description"),
        image_url=f.url(f.nested(raw, "coverImage", "large"), "coverImage.large"),
        anilist_url=f.url(raw.get("siteUrl"), "siteUrl"),
        start_year=start_year,
        end_year=end_year,
    )


# --- Optional field rules ------------------------------------------------------


class _OptionalFields:
    """Converters for optional fields: None in, None out; invalid in, None out + warning."""

    def __init__(self, anilist_id: int):
        self.anilist_id = anilist_id

    def warn(self, field: str, value: Any, problem: str) -> None:
        logger.warning("AniList anime %d: %s %s (%s); stored as NULL", self.anilist_id, field, problem, _short(value))

    def nested(self, raw: dict[str, Any], key: str, inner: str) -> Any:
        container = raw.get(key)
        if container is None:
            return None
        if not isinstance(container, dict):
            self.warn(key, container, "is not an object")
            return None
        return container.get(inner)

    def text(self, value: Any, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            self.warn(field, value, "is not text")
            return None
        return _clean_text(value) or None

    def whole_number(self, value: Any, field: str, minimum: int) -> int | None:
        if value is None:
            return None
        if not _is_whole_number(value) or not minimum <= value <= MAX_INTEGER:
            self.warn(field, value, f"is not a whole number from {minimum} to {MAX_INTEGER}")
            return None
        return value

    def score(self, value: Any, field: str) -> Decimal | None:
        """AniList's 0-100 weightedScore -> our 0-10 score with 2 decimals (85 -> 8.50)."""
        if value is None:
            return None
        is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        if not is_number or not math.isfinite(value) or not 0 <= value <= 100:
            self.warn(field, value, "is not a number between 0 and 100")
            return None
        # Via str() so a float like 85.3 becomes exactly 85.3, not 85.29999...
        return (Decimal(str(value)) / 10).quantize(Decimal("0.01"))

    def date(self, value: Any, field: str) -> date | None:
        """{year, month, day} -> date. Any missing part -> None (normal, no warning)."""
        if value is None:
            return None
        if not isinstance(value, dict):
            self.warn(field, value, "is not an object")
            return None
        year, month, day = value.get("year"), value.get("month"), value.get("day")
        if year is None or month is None or day is None:
            return None  # partial dates are common (e.g. unreleased anime)
        if not (_is_whole_number(year) and _is_whole_number(month) and _is_whole_number(day)):
            self.warn(field, value, "has a part that is not a whole number")
            return None
        try:
            return date(year, month, day)
        except ValueError:  # e.g. February 30th, or month 13
            self.warn(field, value, "is not a real calendar date")
            return None

    def year(self, value: Any, field: str) -> int | None:
        """The year of a {year, month, day} date, kept even when month or day is missing."""
        if not isinstance(value, dict) or value.get("year") is None:
            return None  # missing is normal; a non-object was already reported by date()
        year = value["year"]
        if not _is_whole_number(year) or not date.min.year <= year <= date.max.year:
            # With all three parts present, date() has already warned about this value.
            if value.get("month") is None or value.get("day") is None:
                self.warn(field, value, "has a year that is not a real year")
            return None
        return year

    def url(self, value: Any, field: str) -> str | None:
        """Only http(s) URLs: rejects things like javascript: links."""
        text = self.text(value, field)
        if text is None:
            return None
        parts = urlsplit(text)
        if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
            self.warn(field, text, "is not an http(s) URL")
            return None
        return text

    def synopsis(self, value: Any, field: str) -> str | None:
        text = self.text(value, field)
        return _html_to_plain_text(text) if text is not None else None


# --- Helpers -------------------------------------------------------------------

_LINE_BREAK_TAG = re.compile(r"<br\s*/?>|</?(?:p|ul|ol)\b[^>]*>", re.IGNORECASE)
_LIST_ITEM_TAG = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")
_THREE_OR_MORE_NEWLINES = re.compile(r"\n{3,}")


def _html_to_plain_text(text: str) -> str | None:
    """Convert AniList's description (which contains HTML despite asHtml: false) to plain text.

    Keeps paragraphs and list items readable and keeps "(Source: ...)" credits.
    """
    text = _LINE_BREAK_TAG.sub("\n", text)  # <br>, <p>, <ul> ... -> line break
    text = _LIST_ITEM_TAG.sub("\n• ", text)  # <li> -> bullet on a new line
    text = _ANY_TAG.sub("", text)  # remove every other tag, keep its text
    text = html.unescape(text)  # &mdash; -> —, &amp; -> &
    text = "\n".join(line.strip() for line in text.split("\n"))  # spaces around line breaks
    text = _THREE_OR_MORE_NEWLINES.sub("\n\n", text)  # at most one blank line
    return text.strip() or None


def _clean_text(text: str) -> str:
    """Trim the text and drop NUL characters, which PostgreSQL cannot store in TEXT."""
    return text.replace("\x00", "").strip()


def _is_whole_number(value: object) -> TypeGuard[int]:
    # bool is a subclass of int in Python (True == 1), so it must be excluded explicitly.
    return isinstance(value, int) and not isinstance(value, bool)


def _short(value: Any, limit: int = 80) -> str:
    """repr() of a value, truncated so untrusted data can't flood the logs."""
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "..."
