"""The API's JSON shapes, mirroring the schemas in openapi.yaml (the contract, ADR 0010).

These Pydantic models are the API's own models, separate from the domain
and the use cases: the contract can change how something is shown without
touching the business code, and the other way round.

- Response models are built from the use cases' data with the from_* functions.
  They forbid extra fields, so a field the contract doesn't declare can't leak out.
- WatchlistEntryInput validates the PUT body. It is strict: "5" is not an
  integer and true is not a number, exactly as the JSON Schema in the contract says.

Schemathesis checks every response against openapi.yaml, so a drift between
these models and the contract fails the tests.
"""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from animeverse.application.ports import CatalogAnime, FranchiseCount, FranchiseRef, Page, StoredWatchlistEntry
from animeverse.domain.watchlist import MAX_EPISODES_WATCHED, MAX_NOTES_LENGTH, MAX_RATING, MIN_RATING, WatchStatus


class _Response(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Responses ----------------------------------------------------------------------------


class FranchiseRefOut(_Response):
    id: int
    name: str


class FranchiseOut(_Response):
    id: int
    name: str
    anime_count: int


class FranchiseListOut(_Response):
    data: list[FranchiseOut]


class WatchlistEntryOut(_Response):
    anime_id: int
    status: WatchStatus
    episodes_watched: int
    rating: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AnimeSummaryOut(_Response):
    id: int
    anilist_id: int
    title: str
    title_english: str | None
    title_japanese: str | None
    format: str | None
    status: str | None
    episodes: int | None
    start_year: int | None
    end_year: int | None
    score: float | None
    popularity: int | None
    image_url: str | None
    franchises: list[FranchiseRefOut]
    watchlist_entry: WatchlistEntryOut | None


class AnimeDetailOut(AnimeSummaryOut):
    mal_id: int | None
    synopsis: str | None
    aired_from: date | None
    aired_to: date | None
    anilist_url: str | None
    updated_at: datetime


class PageMetaOut(_Response):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PageLinksOut(_Response):
    self: str
    next: str | None
    prev: str | None


class AnimePageOut(_Response):
    data: list[AnimeSummaryOut]
    meta: PageMetaOut
    links: PageLinksOut


def from_watchlist_entry(stored: StoredWatchlistEntry | None) -> WatchlistEntryOut | None:
    if stored is None:
        return None
    return WatchlistEntryOut(
        anime_id=stored.anime_id,
        status=stored.entry.status,
        episodes_watched=stored.entry.episodes_watched,
        rating=stored.entry.rating,
        notes=stored.entry.notes,
        created_at=stored.created_at,
        updated_at=stored.updated_at,
    )


def _summary_fields(item: CatalogAnime) -> dict[str, object]:
    anime = item.anime
    return {
        "id": item.id,
        "anilist_id": anime.anilist_id,
        "title": anime.title,
        "title_english": anime.title_english,
        "title_japanese": anime.title_japanese,
        "format": anime.type,  # stored as anime.type; the contract calls it format, as AniList does
        "status": anime.status,
        "episodes": anime.episodes,
        "start_year": anime.start_year,
        "end_year": anime.end_year,
        "score": float(anime.score) if anime.score is not None else None,  # Decimal("8.20") -> 8.2
        "popularity": anime.popularity,
        "image_url": anime.image_url,
        "franchises": [_franchise_ref(f) for f in item.franchises],
        "watchlist_entry": from_watchlist_entry(item.watchlist_entry),
    }


def _franchise_ref(ref: FranchiseRef) -> FranchiseRefOut:
    return FranchiseRefOut(id=ref.id, name=ref.name)


def from_summary(item: CatalogAnime) -> AnimeSummaryOut:
    return AnimeSummaryOut.model_validate(_summary_fields(item))


def from_detail(item: CatalogAnime) -> AnimeDetailOut:
    anime = item.anime
    return AnimeDetailOut.model_validate(
        {
            **_summary_fields(item),
            "mal_id": anime.mal_id,
            "synopsis": anime.synopsis,
            "aired_from": anime.aired_from,
            "aired_to": anime.aired_to,
            "anilist_url": anime.anilist_url,
            "updated_at": item.updated_at,
        }
    )


def from_page(page: Page[CatalogAnime], links: PageLinksOut) -> AnimePageOut:
    return AnimePageOut(
        data=[from_summary(item) for item in page.items],
        meta=PageMetaOut(
            page=page.request.number,
            page_size=page.request.size,
            total_items=page.total_items,
            total_pages=page.total_pages,
        ),
        links=links,
    )


def from_franchises(franchises: list[FranchiseCount]) -> FranchiseListOut:
    return FranchiseListOut(data=[FranchiseOut(id=f.id, name=f.name, anime_count=f.anime_count) for f in franchises])


# --- Request body -------------------------------------------------------------------------


# Text without NUL characters (PostgreSQL text can't hold them), as openapi.yaml says.
NO_NUL = r"^[^\x00]*$"


class WatchlistEntryInput(BaseModel):
    """The PUT body. Every field is required; null means "no rating" / "no notes"."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["planning", "watching", "completed", "paused", "dropped"]
    episodes_watched: Annotated[int, Field(ge=0, le=MAX_EPISODES_WATCHED)]
    rating: Annotated[int, Field(ge=MIN_RATING, le=MAX_RATING)] | None
    notes: Annotated[str, Field(max_length=MAX_NOTES_LENGTH, pattern=NO_NUL)] | None
