// How every value is shown. A null is always said out loud ("unknown", "unscored"),
// never left blank or turned into zero.
import type { AnimeSummary, WatchStatus } from "../api/types";

const RELEASE_STATUS: Record<string, string> = {
  FINISHED: "Finished",
  RELEASING: "Releasing",
  NOT_YET_RELEASED: "Not yet released",
  CANCELLED: "Cancelled",
  HIATUS: "On hiatus",
};

const FORMAT: Record<string, string> = {
  TV: "TV",
  TV_SHORT: "TV short",
  MOVIE: "Movie",
  SPECIAL: "Special",
  OVA: "OVA",
  ONA: "ONA",
  MUSIC: "Music",
};

const WATCH_STATUS: Record<WatchStatus, string> = {
  planning: "Planning",
  watching: "Watching",
  completed: "Completed",
  paused: "Paused",
  dropped: "Dropped",
};

/** An unknown future value from AniList, e.g. `SOME_VALUE` -> "Some value". */
function humanize(value: string): string {
  const words = value.toLowerCase().replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function releaseStatusLabel(status: string | null): string {
  if (status === null) return "Release status unknown";
  return RELEASE_STATUS[status] ?? humanize(status);
}

export function formatLabel(format: string | null): string {
  if (format === null) return "Format unknown";
  return FORMAT[format] ?? humanize(format);
}

export function watchStatusLabel(status: WatchStatus): string {
  return WATCH_STATUS[status];
}

export function scoreLabel(score: number | null): string {
  return score === null ? "Unscored" : `${score.toFixed(1)} / 10`;
}

export function startYearLabel(year: number | null): string {
  return year === null ? "Start year unknown" : String(year);
}

export function popularityLabel(popularity: number | null): string {
  return popularity === null
    ? "Popularity unknown"
    : `${popularity.toLocaleString("en-GB")} on AniList lists`;
}

export function episodesLabel(episodes: number | null): string {
  if (episodes === null) return "Episodes unknown";
  return episodes === 1 ? "1 episode" : `${episodes} episodes`;
}

/** "Episode 110 of 500", or "Episode 12 of unknown" when the total isn't known. */
export function progressLabel(watched: number, episodes: number | null): string {
  return `Episode ${watched} of ${episodes === null ? "unknown" : episodes}`;
}

export function englishTitleLabel(anime: Pick<AnimeSummary, "title_english">): string {
  return anime.title_english ?? "No English title";
}

export function franchiseNames(anime: Pick<AnimeSummary, "franchises">): string {
  if (anime.franchises.length === 0) return "No franchise";
  return anime.franchises.map((f) => f.name).join(" and ");
}

/** The accessible name of a star: title, franchise, score or "unscored", watchlist. */
export function starAccessibleName(anime: AnimeSummary, filteredOut = false): string {
  const parts = [
    anime.title,
    franchiseNames(anime),
    anime.score === null ? "unscored" : `score ${anime.score.toFixed(1)} of 10`,
  ];
  const entry = anime.watchlist_entry;
  if (entry) {
    parts.push(
      entry.status === "watching"
        ? `watching, ${progressLabel(entry.episodes_watched, anime.episodes).toLowerCase()}`
        : `on your watchlist: ${watchStatusLabel(entry.status).toLowerCase()}`,
    );
  }
  if (filteredOut) parts.push("does not match the filters");
  return parts.join(", ");
}

/** "No. 48 · 23 November 2026": the ISO week of the year is the issue number. */
export function issueLabel(date: Date): { number: string; date: string } {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7);
  return {
    number: `No. ${week}`,
    date: new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric" }).format(date),
  };
}
