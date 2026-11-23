// The Browse page's state lives in the URL, with the API's own parameter names, so a
// filtered view survives a reload and can be bookmarked. These pure functions translate
// between the browser's query string and the typed query of `GET /v1/anime`.
//
// Parsing only checks the *shape* of each value (a whole number, a number, a known enum
// value, true/false). Ranges and rules between fields (e.g. `year_to` before
// `year_from`) are left to the API, whose validation errors are shown next to the
// matching control.
import type { AnimeFormat, AnimeListQuery, ReleaseStatus, WatchStatus } from "../api/types";

export const RELEASE_STATUSES: readonly ReleaseStatus[] = [
  "FINISHED",
  "RELEASING",
  "NOT_YET_RELEASED",
  "CANCELLED",
  "HIATUS",
];
export const FORMATS: readonly AnimeFormat[] = ["TV", "TV_SHORT", "MOVIE", "SPECIAL", "OVA", "ONA", "MUSIC"];
export const WATCH_STATUSES: readonly WatchStatus[] = ["planning", "watching", "completed", "paused", "dropped"];

export type SortValue = NonNullable<AnimeListQuery["sort"]>;
export const SORTS: readonly { value: SortValue; label: string }[] = [
  { value: "-popularity", label: "Most popular first" },
  { value: "popularity", label: "Least popular first" },
  { value: "-score", label: "Highest score first" },
  { value: "score", label: "Lowest score first" },
  { value: "-start_year", label: "Newest first" },
  { value: "start_year", label: "Oldest first" },
  { value: "title", label: "Title A to Z" },
  { value: "-title", label: "Title Z to A" },
];
/** The API's default order (the contract's `sort` default). */
export const DEFAULT_SORT: SortValue = "-popularity";
/** The API's default page size (the contract's `page_size` default). */
export const DEFAULT_PAGE_SIZE = 24;

/** Every parameter, in the order they are written to the URL. */
export const PARAMS = [
  "q",
  "franchise",
  "status",
  "format",
  "year_from",
  "year_to",
  "min_score",
  "on_watchlist",
  "watchlist_status",
  "sort",
  "page",
  "page_size",
] as const satisfies readonly (keyof AnimeListQuery)[];

export type Param = (typeof PARAMS)[number];

/** The parameters that narrow the results (everything but sort and paging). */
export const FILTER_PARAMS = [
  "q",
  "franchise",
  "status",
  "format",
  "year_from",
  "year_to",
  "min_score",
  "on_watchlist",
  "watchlist_status",
] as const satisfies readonly Param[];

export type FilterParam = (typeof FILTER_PARAMS)[number];

const INTEGER = /^-?\d+$/;
const NUMBER = /^-?(\d+(\.\d*)?|\.\d+)$/;

function integer(value: string | null): number | undefined {
  if (value === null || !INTEGER.test(value.trim())) return undefined;
  const n = Number(value);
  return Number.isSafeInteger(n) ? n : undefined;
}

function number(value: string | null): number | undefined {
  if (value === null || !NUMBER.test(value.trim())) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function oneOf<T extends string>(values: readonly T[], value: string | null): T | undefined {
  return value !== null && (values as readonly string[]).includes(value) ? (value as T) : undefined;
}

/**
 * Reads the Browse state from a query string. Values of the wrong shape and unknown
 * parameters are ignored (never sent to the API), so a hand-edited URL can't break the page.
 */
export function parseBrowseQuery(search: URLSearchParams | string): AnimeListQuery {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const q = params.get("q");
  const onWatchlist = params.get("on_watchlist");
  const query: AnimeListQuery = {
    q: q !== null && q.trim() !== "" ? q : undefined,
    franchise: integer(params.get("franchise")),
    status: oneOf(RELEASE_STATUSES, params.get("status")),
    format: oneOf(FORMATS, params.get("format")),
    year_from: integer(params.get("year_from")),
    year_to: integer(params.get("year_to")),
    min_score: number(params.get("min_score")),
    on_watchlist: onWatchlist === "true" ? true : onWatchlist === "false" ? false : undefined,
    watchlist_status: oneOf(WATCH_STATUSES, params.get("watchlist_status")),
    sort: oneOf(
      SORTS.map((s) => s.value),
      params.get("sort"),
    ),
    page: integer(params.get("page")),
    page_size: integer(params.get("page_size")),
  };
  return compact(query);
}

/** Drops undefined entries, keeping the parameter order. */
function compact(query: AnimeListQuery): AnimeListQuery {
  const out: Record<string, unknown> = {};
  for (const key of PARAMS) {
    const value = query[key];
    if (value !== undefined) out[key] = value;
  }
  return out as AnimeListQuery;
}

/** Writes the Browse state as a query string, parameters in a stable order. */
export function toSearchParams(query: AnimeListQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of PARAMS) {
    const value = query[key];
    if (value !== undefined) params.set(key, String(value));
  }
  return params;
}

/** The Browse URL for a query. */
export function browseHref(query: AnimeListQuery): string {
  const search = toSearchParams(query).toString();
  return search ? `/anime?${search}` : "/anime";
}

/**
 * The Browse URL for one of the API's own page links (`links.next` / `links.prev`): the
 * link's query string is used exactly as the API wrote it.
 */
export function browseHrefFromApiLink(link: string): string {
  const url = new URL(link, "http://animeverse.local");
  return url.search ? `/anime${url.search}` : "/anime";
}

/**
 * The query with one filter changed. Any change of filter, sort or page size goes back to
 * the first page (the old page number may not exist any more).
 */
export function withParam<K extends Param>(
  query: AnimeListQuery,
  key: K,
  value: AnimeListQuery[K] | undefined,
): AnimeListQuery {
  const next: AnimeListQuery = { ...query, [key]: value };
  if (key !== "page") delete next.page;
  return compact(next);
}

/** The query without any filter (sort and page size are kept). */
export function withoutFilters(query: AnimeListQuery): AnimeListQuery {
  return compact({ sort: query.sort, page_size: query.page_size });
}

export function activeFilters(query: AnimeListQuery): FilterParam[] {
  return FILTER_PARAMS.filter((key) => query[key] !== undefined);
}
