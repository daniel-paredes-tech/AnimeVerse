import { useMemo, useState } from "react";
import { Link } from "react-router";
import type { AnimeSummary } from "../api/types";
import {
  formatLabel,
  franchiseNames,
  progressLabel,
  releaseStatusLabel,
  scoreLabel,
  watchStatusLabel,
} from "../lib/labels";

type SortKey = "title" | "franchise" | "start_year" | "score" | "popularity";
interface Sort {
  key: SortKey;
  descending: boolean;
}

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "title", label: "Title", numeric: false },
  { key: "franchise", label: "Franchise", numeric: false },
  { key: "start_year", label: "Started", numeric: true },
  { key: "score", label: "Score", numeric: true },
  { key: "popularity", label: "Popularity", numeric: true },
];

function value(a: AnimeSummary, key: SortKey): string | number | null {
  switch (key) {
    case "title":
      return a.title;
    case "franchise":
      return a.franchises.length ? franchiseNames(a) : null;
    case "start_year":
      return a.start_year;
    case "score":
      return a.score;
    case "popularity":
      return a.popularity;
  }
}

/** Unknown values always go last, whatever the direction (like the API's own sort). */
function compare(a: AnimeSummary, b: AnimeSummary, sort: Sort): number {
  const va = value(a, sort.key);
  const vb = value(b, sort.key);
  if (va === null && vb === null) return a.id - b.id;
  if (va === null) return 1;
  if (vb === null) return -1;
  const order = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
  return (sort.descending ? -order : order) || a.id - b.id;
}

function SortMark({ descending }: { descending: boolean }) {
  return (
    <svg className="sort-mark" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">
      <path d={descending ? "M1 3h8L5 8z" : "M1 7h8L5 2z"} />
    </svg>
  );
}

/** The map as a table: the same anime, sortable, for keyboards and screen readers. */
export function UniverseList({ anime, total }: { anime: readonly AnimeSummary[]; total: number }) {
  const [sort, setSort] = useState<Sort>({ key: "popularity", descending: true });
  const rows = useMemo(() => [...anime].sort((a, b) => compare(a, b, sort)), [anime, sort]);

  const toggle = (key: SortKey, numeric: boolean) =>
    setSort((old) => (old.key === key ? { key, descending: !old.descending } : { key, descending: numeric }));

  return (
    <div className="universe-list">
      <table>
        <caption>
          {anime.length === total ? `All ${total} anime` : `${anime.length} of ${total} anime match the filters`}, sorted
          by {COLUMNS.find((c) => c.key === sort.key)!.label.toLowerCase()} ({sort.descending ? "high to low" : "low to high"}
          , unknown last)
        </caption>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={column.numeric ? "num" : undefined}
                aria-sort={sort.key === column.key ? (sort.descending ? "descending" : "ascending") : undefined}
              >
                <button type="button" onClick={() => toggle(column.key, column.numeric)}>
                  {column.label}
                  {sort.key === column.key ? <SortMark descending={sort.descending} /> : null}
                </button>
              </th>
            ))}
            <th scope="col">Format</th>
            <th scope="col">Release status</th>
            <th scope="col">Watchlist</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.id}>
              <th scope="row">
                <Link to={`/anime/${a.id}`}>{a.title}</Link>
                {a.title_english && a.title_english !== a.title ? (
                  <span className="universe-list__english">{a.title_english}</span>
                ) : null}
              </th>
              <td>{franchiseNames(a)}</td>
              <td className="num">{a.start_year ?? "Unknown"}</td>
              <td className="num">{a.score === null ? "Unscored" : scoreLabel(a.score)}</td>
              <td className="num">{a.popularity === null ? "Unknown" : a.popularity.toLocaleString("en-GB")}</td>
              <td>{formatLabel(a.format)}</td>
              <td>{releaseStatusLabel(a.status)}</td>
              <td>
                {a.watchlist_entry
                  ? a.watchlist_entry.status === "watching"
                    ? `Watching, ${progressLabel(a.watchlist_entry.episodes_watched, a.episodes).toLowerCase()}`
                    : watchStatusLabel(a.watchlist_entry.status)
                  : "Not on it"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
