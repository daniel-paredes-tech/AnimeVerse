"""Internal data models.

These describe AnimeVerse's own data, matching db/schema.sql. They are
deliberately separate from Jikan's JSON format: the parser converts API
responses into these models, and the repository saves them.

The models hold data only. Validation happens in the parser, before a model
is created.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Franchise:
    """A franchise we import, e.g. Naruto. This is our data, not Jikan's."""

    name: str  # display name, e.g. "Attack on Titan"
    search_query: str  # the text sent to Jikan's search as q=...


@dataclass(frozen=True)
class Anime:
    """One anime, with the fields approved for storage."""

    mal_id: int
    title: str
    title_english: str | None = None
    title_japanese: str | None = None
    type: str | None = None
    episodes: int | None = None
    status: str | None = None
    aired_from: date | None = None
    aired_to: date | None = None
    score: Decimal | None = None  # Decimal, to match NUMERIC(4,2) exactly
    rank: int | None = None
    popularity: int | None = None
    synopsis: str | None = None
    image_url: str | None = None
    mal_url: str | None = None
