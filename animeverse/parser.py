"""Parser: turns raw AniList media dicts into validated Anime models.

The parser is the gatekeeper for untrusted API data. Everything after it
(the repository, the database) can rely on clean, correctly typed values.

Policy:
- A missing or invalid REQUIRED field (id, title.romaji) rejects the item.
- An invalid OPTIONAL field becomes None (NULL) and a warning is logged.
  A merely missing optional value is normal and logged as nothing.
- parse_anime_list never raises for a bad item: one malformed record must
  not stop the rest of the import.
"""

import html
import logging
import math
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

from animeverse.models import Anime

logger = logging.getLogger(__name__)

# Largest value of a PostgreSQL INTEGER column. A bigger number would make the
# INSERT fail, so the parser refuses it here instead.
MAX_INTEGER = 2_147_483_647


class InvalidAnimeError(Exception):
    """Raised when an item cannot become an Anime (a required field is bad)."""


@dataclass(frozen=True)
class Rejection:
    position: int  # index of the item in the list that was parsed
    anilist_id: int | None  # known only if the item had a valid id
    reason: str


@dataclass(frozen=True)
class ParseResult:
    valid: list[Anime]
    rejected: list[Rejection]


# --- Public interface ----------------------------------------------------------


def parse_anime_list(raw_items: list[Any]) -> ParseResult:
    """Parse many items. Bad items are collected as rejections, never raised."""
    valid: list[Anime] = []
    rejected: list[Rejection] = []
    for position, raw in enumerate(raw_items):
        try:
            valid.append(parse_anime(raw))
        except InvalidAnimeError as exc:
            raw_id = raw.get("id") if isinstance(raw, dict) else None
            anilist_id = raw_id if _is_whole_number(raw_id) else None
            rejected.append(Rejection(position, anilist_id, str(exc)))
            logger.warning("Rejected AniList item at position %d (id=%s): %s", position, anilist_id, exc)
    return ParseResult(valid, rejected)


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
    if aired_from and aired_to and aired_to < aired_from:
        f.warn("endDate", aired_to, "is before startDate")
        aired_to = None

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
    )


# --- Optional field rules ------------------------------------------------------


class _OptionalFields:
    """Converters for optional fields: None in, None out; invalid in, None out + warning."""

    def __init__(self, anilist_id: int):
        self.anilist_id = anilist_id

    def warn(self, field: str, value: Any, problem: str) -> None:
        logger.warning(
            "AniList anime %d: %s %s (%s); stored as NULL", self.anilist_id, field, problem, _short(value)
        )

    def nested(self, raw: dict, key: str, inner: str) -> Any:
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
        parts = (value.get("year"), value.get("month"), value.get("day"))
        if any(part is None for part in parts):
            return None  # partial dates are common (e.g. unreleased anime)
        if not all(_is_whole_number(part) for part in parts):
            self.warn(field, value, "has a part that is not a whole number")
            return None
        try:
            return date(*parts)
        except ValueError:  # e.g. February 30th, or month 13
            self.warn(field, value, "is not a real calendar date")
            return None

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


def _is_whole_number(value: Any) -> bool:
    # bool is a subclass of int in Python (True == 1), so it must be excluded explicitly.
    return isinstance(value, int) and not isinstance(value, bool)


def _short(value: Any, limit: int = 80) -> str:
    """repr() of a value, truncated so untrusted data can't flood the logs."""
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "..."
