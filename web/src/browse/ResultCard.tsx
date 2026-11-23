import { Link } from "react-router";
import type { AnimeSummary } from "../api/types";
import {
  formatLabel,
  franchiseNames,
  progressLabel,
  releaseStatusLabel,
  scoreLabel,
  startYearLabel,
  watchStatusLabel,
} from "../lib/labels";
import { PAPER } from "../universe/palette";
import { scoreToneStep } from "../universe/screentone";
import { StarGlyph } from "../universe/StarGlyph";

/** The id prefix of the tone patterns that BrowsePage defines once for every card. */
export const BROWSE_TONE_PREFIX = "browse";

interface ResultCardProps {
  anime: AnimeSummary;
  stocks: ReadonlyMap<number, string>;
}

/** One entry of the series index: cover, titles, the facts, score as tone. */
export function ResultCard({ anime, stocks }: ResultCardProps) {
  const first = anime.franchises[0];
  const stock = first ? stocks.get(first.id) ?? PAPER : PAPER;
  const entry = anime.watchlist_entry;
  const titleId = `entry-${anime.id}`;

  return (
    <li className="entry">
      <article aria-labelledby={titleId}>
        {/* The franchise's stock as a printed edge: colour only, no label above the title. */}
        <div className="entry__edge" style={{ backgroundColor: stock }} aria-hidden="true" />
        <div className="entry__body">
          {anime.image_url ? (
            <img className="entry__cover" src={anime.image_url} alt="" width={84} height={120} loading="lazy" />
          ) : (
            <span className="entry__cover entry__cover--none">No cover image</span>
          )}
          <div className="entry__text">
            <h3 className="entry__title" id={titleId}>
              <Link className="entry__link" to={`/anime/${anime.id}`}>
                {anime.title}
              </Link>
            </h3>
            <p className={anime.title_english ? "entry__english" : "entry__english entry__unknown"}>
              {anime.title_english ?? "No English title"}
            </p>
            <dl className="entry__facts">
              <div className="entry__fact--wide">
                <dt>Franchise</dt>
                <dd>{franchiseNames(anime)}</dd>
              </div>
              <div>
                <dt>Format</dt>
                <dd>{anime.format === null ? "Unknown" : formatLabel(anime.format)}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{anime.status === null ? "Unknown" : releaseStatusLabel(anime.status)}</dd>
              </div>
              <div>
                <dt>Started</dt>
                <dd>{anime.start_year === null ? "Unknown" : startYearLabel(anime.start_year)}</dd>
              </div>
              <div>
                <dt>Episodes</dt>
                <dd>{anime.episodes === null ? "Unknown" : anime.episodes}</dd>
              </div>
              <div>
                <dt>Popularity</dt>
                <dd>{anime.popularity === null ? "Unknown" : anime.popularity.toLocaleString("en-GB")}</dd>
              </div>
            </dl>
          </div>
          <div className="entry__score">
            <svg viewBox="-18 -18 36 36" width="36" height="36" aria-hidden="true">
              <StarGlyph r={15} stock={stock} toneStep={scoreToneStep(anime.score)} idPrefix={BROWSE_TONE_PREFIX} />
            </svg>
            <span className={anime.score === null ? "entry__score-value entry__unknown" : "entry__score-value"}>
              {anime.score === null ? "Unscored" : scoreLabel(anime.score)}
            </span>
          </div>
        </div>
        <p className={`entry__watch${entry ? " entry__watch--on" : ""}`}>
          {entry
            ? entry.status === "watching"
              ? `Watching · ${progressLabel(entry.episodes_watched, anime.episodes)}`
              : `On your watchlist · ${watchStatusLabel(entry.status)}`
            : "Not on your watchlist"}
        </p>
      </article>
    </li>
  );
}
