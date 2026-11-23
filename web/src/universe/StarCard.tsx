import { useLayoutEffect, useRef, useState } from "react";
import type { AnimeSummary } from "../api/types";
import {
  englishTitleLabel,
  formatLabel,
  franchiseNames,
  progressLabel,
  scoreLabel,
  startYearLabel,
  watchStatusLabel,
} from "../lib/labels";

export interface CardAnchor {
  /** Star centre and radius in pixels, relative to the panel. */
  x: number;
  y: number;
  r: number;
}

interface StarCardProps {
  anime: AnimeSummary;
  anchor: CardAnchor;
  panel: { width: number; height: number };
  onPointerEnter: () => void;
  onPointerLeave: () => void;
  onOpen: () => void;
}

/**
 * The cover card of a hovered or focused star. It repeats what the star's accessible
 * name already says, so it is hidden from screen readers. The pointer can move onto it
 * without it closing, and Esc closes it.
 */
export function StarCard({ anime, anchor, panel, onPointerEnter, onPointerLeave, onOpen }: StarCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    const card = ref.current;
    if (!card) return;
    const { width, height } = card.getBoundingClientRect();
    const gap = 10;
    const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));
    const fitsRight = anchor.x + anchor.r + gap + width <= panel.width - 8;
    const fitsLeft = anchor.x - anchor.r - gap - width >= 8;
    let left: number;
    let top: number;
    if (fitsRight || fitsLeft) {
      left = fitsRight ? anchor.x + anchor.r + gap : anchor.x - anchor.r - gap - width;
      top = anchor.y - height / 2;
    } else {
      // A narrow panel: centre the card under (or over) the star instead.
      left = clamp(anchor.x - width / 2, 8, panel.width - width - 8);
      top = anchor.y + anchor.r + gap;
      if (top + height > panel.height - 8) top = anchor.y - anchor.r - gap - height;
    }
    setPosition({ left, top: clamp(top, 8, panel.height - height - 8) });
  }, [anchor.x, anchor.y, anchor.r, panel.width, panel.height, anime.id]);

  const entry = anime.watchlist_entry;
  return (
    <div
      ref={ref}
      className="star-card"
      aria-hidden="true"
      style={position ? { left: position.left, top: position.top } : { left: 0, top: 0, visibility: "hidden" }}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
      onClick={onOpen}
    >
      {anime.image_url ? (
        <img className="star-card__cover" src={anime.image_url} alt="" width={76} height={108} />
      ) : (
        <div className="star-card__cover star-card__cover--none">No cover image</div>
      )}
      <div className="star-card__text">
        <p className="star-card__title">{anime.title}</p>
        <p className={anime.title_english ? "star-card__sub" : "star-card__sub star-card__unknown"}>
          {englishTitleLabel(anime)}
        </p>
        <p className="star-card__sub" lang={anime.title_japanese ? "ja" : undefined}>
          {anime.title_japanese ?? <span className="star-card__unknown">No native title</span>}
        </p>
        <dl className="star-card__facts">
          <div>
            <dt>Started</dt>
            <dd>{startYearLabel(anime.start_year)}</dd>
          </div>
          <div>
            <dt>Score</dt>
            <dd className={anime.score === null ? "star-card__unknown" : undefined}>{scoreLabel(anime.score)}</dd>
          </div>
          <div>
            <dt>Format</dt>
            <dd>{formatLabel(anime.format)}</dd>
          </div>
          <div>
            <dt>Franchise</dt>
            <dd>{franchiseNames(anime)}</dd>
          </div>
        </dl>
        <p className="star-card__watch">
          {entry
            ? entry.status === "watching"
              ? `Watching · ${progressLabel(entry.episodes_watched, anime.episodes)}`
              : `On your watchlist · ${watchStatusLabel(entry.status)}`
            : "Not on your watchlist"}
        </p>
      </div>
    </div>
  );
}
