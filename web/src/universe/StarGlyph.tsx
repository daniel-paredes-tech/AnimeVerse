import type { WatchlistEntry } from "../api/types";
import { FRANCHISE_STOCKS, INK, MASTHEAD_RED, PAPER, toneInkFor } from "./palette";
import { SCORE_TONE_PITCH, progressArc, sparklePath, toneDotRadius } from "./screentone";

const ALL_STEPS = Array.from({ length: 21 }, (_, i) => i);
const ALL_STOCKS: readonly string[] = [...FRANCHISE_STOCKS, PAPER];

/** The id of the dot pattern for one stock and score step. */
export function tonePatternId(idPrefix: string, stock: string, step: number): string {
  return `${idPrefix}-tone-${stock.replace("#", "").toLowerCase()}-${step}`;
}

/**
 * One dot pattern per stock and score step (half points). Each franchise's dots are
 * printed in its stock's deep shade (ink on plain paper): a screen, never a grey fill.
 */
export function ToneDefs({
  idPrefix,
  steps = ALL_STEPS,
  stocks = ALL_STOCKS,
}: {
  idPrefix: string;
  steps?: readonly number[];
  stocks?: readonly string[];
}) {
  const pitch = SCORE_TONE_PITCH;
  return (
    <>
      {stocks.flatMap((stock) =>
        steps.map((step) => (
          <pattern
            key={`${stock}-${step}`}
            id={tonePatternId(idPrefix, stock, step)}
            patternUnits="userSpaceOnUse"
            width={pitch}
            height={pitch}
            patternTransform="rotate(45)"
          >
            {step > 0 ? <circle cx={pitch / 2} cy={pitch / 2} r={toneDotRadius(step)} fill={toneInkFor(stock)} /> : null}
          </pattern>
        )),
      )}
    </>
  );
}

interface StarGlyphProps {
  r: number;
  stock: string;
  /** Score tone step (0..20), or null for an unscored, untoned star. */
  toneStep: number | null;
  idPrefix: string;
  /** Drawn as a faint outline: the star doesn't match the filters. */
  dim?: boolean;
  entry?: WatchlistEntry | null;
  episodes?: number | null;
}

/** A four-point sparkle: stock fill, score tone on top, ink outline on a paper keyline. */
export function StarGlyph({ r, stock, toneStep, idPrefix, dim = false, entry = null, episodes = null }: StarGlyphProps) {
  const d = sparklePath(r);
  const ringR = r + 3;
  return (
    <>
      {entry ? <WatchRing r={ringR} entry={entry} episodes={episodes} /> : null}
      {dim ? (
        <path d={d} className="star__ghost" />
      ) : (
        <>
          <path d={d} className="star__keyline" />
          <path d={d} fill={stock} className="star__body" />
          {toneStep !== null && toneStep > 0 ? <path d={d} fill={`url(#${tonePatternId(idPrefix, stock, toneStep)})`} /> : null}
          <path d={d} className="star__outline" />
        </>
      )}
    </>
  );
}

/** The orbit ring of a watchlist entry; `watching` adds a red arc of the episodes watched. */
function WatchRing({ r, entry, episodes }: { r: number; entry: WatchlistEntry; episodes: number | null }) {
  let progress = null;
  if (entry.status === "watching") {
    if (episodes === null || episodes === 0) {
      // The total is unknown: a dotted red ring says so, instead of pretending 0%.
      progress = <circle r={r} className="star__progress star__progress--unknown" stroke={MASTHEAD_RED} />;
    } else {
      const fraction = entry.episodes_watched / episodes;
      const arc = progressArc(0, 0, r, fraction);
      progress =
        fraction >= 1 ? (
          <circle r={r} className="star__progress" stroke={MASTHEAD_RED} />
        ) : arc ? (
          <path d={arc} className="star__progress" stroke={MASTHEAD_RED} />
        ) : null;
    }
  }
  return (
    <>
      {/* Ink on a paper keyline: readable on the dark sky and on a light clearing. */}
      <circle r={r} className="star__ring-keyline" stroke={PAPER} />
      <circle r={r} className="star__ring" stroke={INK} />
      {progress}
    </>
  );
}
