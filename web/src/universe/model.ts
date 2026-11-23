// Turns the API's data into what the universe page shows: franchises, filter options
// and the client-side filter over the loaded anime.
import type { AnimeSummary, Franchise } from "../api/types";
import { formatLabel, releaseStatusLabel } from "../lib/labels";

/** The filter value for "no value" (a null format or release status). */
export const UNKNOWN = "__unknown";

export interface UniverseFilters {
  /** A release status, UNKNOWN, or null for any. */
  status: string | null;
  /** A format, UNKNOWN, or null for any. */
  format: string | null;
}

export const NO_FILTERS: UniverseFilters = { status: null, format: null };

const STATUS_ORDER = ["RELEASING", "NOT_YET_RELEASED", "FINISHED", "HIATUS", "CANCELLED"];
const FORMAT_ORDER = ["TV", "TV_SHORT", "MOVIE", "SPECIAL", "OVA", "ONA", "MUSIC"];

export interface FilterOption {
  value: string;
  label: string;
  count: number;
}

function key(value: string | null): string {
  return value ?? UNKNOWN;
}

export function matchesFilters(anime: AnimeSummary, filters: UniverseFilters): boolean {
  return (
    (filters.status === null || key(anime.status) === filters.status) &&
    (filters.format === null || key(anime.format) === filters.format)
  );
}

export function hasFilters(filters: UniverseFilters): boolean {
  return filters.status !== null || filters.format !== null;
}

/**
 * The values present in the data, in a stable order: the contract's known values first,
 * then any new value AniList might send, then "unknown".
 */
function options(
  anime: readonly AnimeSummary[],
  pick: (a: AnimeSummary) => string | null,
  order: readonly string[],
  label: (value: string | null) => string,
): FilterOption[] {
  const counts = new Map<string, number>();
  for (const a of anime) counts.set(key(pick(a)), (counts.get(key(pick(a))) ?? 0) + 1);
  const rank = (value: string) => {
    if (value === UNKNOWN) return Number.MAX_SAFE_INTEGER;
    const i = order.indexOf(value);
    return i === -1 ? order.length : i;
  };
  return [...counts.entries()]
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .map(([value, count]) => ({ value, count, label: label(value === UNKNOWN ? null : value) }));
}

export function statusOptions(anime: readonly AnimeSummary[]): FilterOption[] {
  return options(anime, (a) => a.status, STATUS_ORDER, (v) => (v === null ? "Unknown" : releaseStatusLabel(v)));
}

export function formatOptions(anime: readonly AnimeSummary[]): FilterOption[] {
  return options(anime, (a) => a.format, FORMAT_ORDER, (v) => (v === null ? "Unknown" : formatLabel(v)));
}

export interface UniverseFranchise {
  id: number;
  name: string;
  /** From `GET /v1/franchises`; for a franchise only seen on an anime, its anime here. */
  animeCount: number;
}

/**
 * The franchises of the map: the franchise list, plus any franchise that an anime
 * references but the list doesn't have (so no anime is ever dropped).
 */
export function mergeFranchises(list: readonly Franchise[], anime: readonly AnimeSummary[]): UniverseFranchise[] {
  const merged = new Map<number, UniverseFranchise>(
    list.map((f) => [f.id, { id: f.id, name: f.name, animeCount: f.anime_count }]),
  );
  for (const a of anime) {
    for (const ref of a.franchises) {
      const existing = merged.get(ref.id);
      if (!existing) merged.set(ref.id, { id: ref.id, name: ref.name, animeCount: 1 });
      else if (!list.some((f) => f.id === ref.id)) existing.animeCount += 1;
    }
  }
  return [...merged.values()].sort((a, b) => a.id - b.id);
}
