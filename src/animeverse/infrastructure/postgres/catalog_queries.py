"""SQL for browsing the catalogue: the filtered, sorted, paginated list, one anime, franchises.

Rules (the same as repository.py):
- Values are always query parameters (%(name)s), never formatted into the SQL.
- Functions never commit and never catch database errors.

The list query is built from fixed pieces, because its WHERE and ORDER BY
depend on the request:
- WHERE: each filter that is present adds one fixed SQL fragment with a
  %(name)s placeholder. The user's values only ever travel as parameters.
- ORDER BY: a column can't be a query parameter, so the sort field is looked
  up in _SORT_COLUMNS, a fixed map. Nothing outside that map can get in.

The behaviour (missing values last, ties by id, literal % and _ in searches)
is pinned down by tests/test_query_contract.py, which runs the same checks
against the in-memory store.
"""

from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from animeverse.application.ports import (
    AnimeFilters,
    CatalogAnime,
    FranchiseCount,
    FranchiseRef,
    Page,
    PageRequest,
    Sort,
    SortField,
    StoredWatchlistEntry,
)
from animeverse.domain.models import Anime
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus

# Every column of the anime, its watchlist entry (NULLs if none) and its
# franchises as a JSON list ordered by name (psycopg turns JSON into Python lists).
_SELECT = """
SELECT a.id, a.anilist_id, a.mal_id, a.title, a.title_english, a.title_japanese,
       a.type, a.episodes, a.status, a.aired_from, a.aired_to, a.score,
       a.popularity, a.synopsis, a.image_url, a.anilist_url, a.start_year,
       a.end_year, a.updated_at,
       w.status AS w_status, w.episodes_watched AS w_episodes_watched,
       w.rating AS w_rating, w.notes AS w_notes,
       w.created_at AS w_created_at, w.updated_at AS w_updated_at,
       COALESCE(
           (SELECT json_agg(json_build_object('id', f.id, 'name', f.name) ORDER BY f.name)
            FROM anime_franchises af
            JOIN franchises f ON f.id = af.franchise_id
            WHERE af.anime_id = a.id),
           '[]'
       ) AS franchises
FROM anime a
LEFT JOIN watchlist_entries w ON w.anime_id = a.id
"""

# The FROM part shared by the list and its count (the count needs no columns).
_FROM = "FROM anime a LEFT JOIN watchlist_entries w ON w.anime_id = a.id"

_SORT_COLUMNS: dict[SortField, sql.Composable] = {
    SortField.POPULARITY: sql.SQL("a.popularity"),
    SortField.SCORE: sql.SQL("a.score"),
    SortField.START_YEAR: sql.SQL("a.start_year"),
    SortField.TITLE: sql.SQL("lower(a.title)"),  # ignoring case
}


def list_anime(conn: psycopg.Connection, filters: AnimeFilters, sort: Sort, page: PageRequest) -> Page[CatalogAnime]:
    """One page of matching anime, plus the number of matches over all pages."""
    where, params = _where(filters)

    count_query = sql.SQL("SELECT count(*) {from_} WHERE {where}").format(from_=sql.SQL(_FROM), where=where)
    count_row = conn.execute(count_query, params).fetchone()
    total: int = count_row[0] if count_row else 0

    direction = sql.SQL("DESC") if sort.descending else sql.SQL("ASC")
    page_query = sql.SQL(
        "{select} WHERE {where} ORDER BY {column} {direction} NULLS LAST, a.id ASC LIMIT %(limit)s OFFSET %(offset)s"
    ).format(select=sql.SQL(_SELECT), where=where, column=_SORT_COLUMNS[sort.field], direction=direction)
    with conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(page_query, {**params, "limit": page.size, "offset": page.offset}).fetchall()

    return Page([_to_catalog_anime(row) for row in rows], total, page)


def get_anime(conn: psycopg.Connection, anime_id: int) -> CatalogAnime | None:
    with conn.cursor(row_factory=dict_row) as cursor:
        row = cursor.execute(sql.SQL(_SELECT + " WHERE a.id = %(id)s"), {"id": anime_id}).fetchone()
    return _to_catalog_anime(row) if row else None


def list_franchises(conn: psycopg.Connection) -> list[FranchiseCount]:
    rows = conn.execute(
        """
        SELECT f.id, f.name, count(af.anime_id)
        FROM franchises f
        LEFT JOIN anime_franchises af ON af.franchise_id = f.id
        GROUP BY f.id, f.name
        ORDER BY f.name
        """
    ).fetchall()
    return [FranchiseCount(id=row[0], name=row[1], anime_count=row[2]) for row in rows]


def _where(f: AnimeFilters) -> tuple[sql.Composable, dict[str, Any]]:
    """The WHERE conditions for the filters that are set (TRUE if none), and their parameters."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if f.text is not None:
        conditions.append(
            "(a.title ILIKE %(pattern)s ESCAPE '\\' OR a.title_english ILIKE %(pattern)s ESCAPE '\\'"
            " OR a.title_japanese ILIKE %(pattern)s ESCAPE '\\')"
        )
        params["pattern"] = f"%{_escape_like(f.text)}%"
    if f.franchise_id is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM anime_franchises af WHERE af.anime_id = a.id AND af.franchise_id = %(franchise_id)s)"
        )
        params["franchise_id"] = f.franchise_id
    if f.status is not None:
        conditions.append("a.status = %(status)s")
        params["status"] = f.status
    if f.format is not None:
        conditions.append("a.type = %(format)s")
        params["format"] = f.format
    if f.year_from is not None:
        conditions.append("a.start_year >= %(year_from)s")  # NULL >= x is not true: no year, left out
        params["year_from"] = f.year_from
    if f.year_to is not None:
        conditions.append("a.start_year <= %(year_to)s")
        params["year_to"] = f.year_to
    if f.min_score is not None:
        conditions.append("a.score >= %(min_score)s")
        params["min_score"] = f.min_score
    if f.on_watchlist is True:
        conditions.append("w.anime_id IS NOT NULL")
    elif f.on_watchlist is False:
        conditions.append("w.anime_id IS NULL")
    if f.watchlist_status is not None:
        conditions.append("w.status = %(watchlist_status)s")
        params["watchlist_status"] = f.watchlist_status.value

    if not conditions:
        return sql.SQL("TRUE"), params
    return sql.SQL(" AND ").join(sql.SQL(c) for c in conditions), params


def _escape_like(text: str) -> str:
    r"""Make %, _ and \ match themselves in a LIKE pattern (backslash is the escape character)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_catalog_anime(row: dict[str, Any]) -> CatalogAnime:
    anime = Anime(
        anilist_id=row["anilist_id"],
        title=row["title"],
        mal_id=row["mal_id"],
        title_english=row["title_english"],
        title_japanese=row["title_japanese"],
        type=row["type"],
        episodes=row["episodes"],
        status=row["status"],
        aired_from=row["aired_from"],
        aired_to=row["aired_to"],
        score=row["score"],
        popularity=row["popularity"],
        synopsis=row["synopsis"],
        image_url=row["image_url"],
        anilist_url=row["anilist_url"],
        start_year=row["start_year"],
        end_year=row["end_year"],
    )
    entry = None
    if row["w_status"] is not None:  # the LEFT JOIN found an entry
        entry = StoredWatchlistEntry(
            anime_id=row["id"],
            entry=WatchlistEntry(
                status=WatchStatus(row["w_status"]),
                episodes_watched=row["w_episodes_watched"],
                rating=row["w_rating"],
                notes=row["w_notes"],
            ),
            created_at=row["w_created_at"],
            updated_at=row["w_updated_at"],
        )
    return CatalogAnime(
        id=row["id"],
        anime=anime,
        franchises=tuple(FranchiseRef(id=f["id"], name=f["name"]) for f in row["franchises"]),
        watchlist_entry=entry,
        updated_at=row["updated_at"],
    )
