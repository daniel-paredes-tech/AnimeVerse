import type { WatchlistEntry } from "../api/types";
import { INK, MASTHEAD_RED, PAPER } from "./palette";
import { SCORE_TONE_PITCH, progressArc, sparklePath, toneDotRadius } from "./screentone";

const ALL_STEPS = Array.from({ length: 21 }, (_, i) => i);

/** One dot pattern per score step (half points). Ink on transparent: no grey anywhere. */
export function ToneDefs({ idPrefix, steps = ALL_STEPS }: { idPrefix: string; steps?: readonly number[] }) {
  const pitch = SCORE_TONE_PITCH;
  return (
    <>
      {steps.map((step) => (
        <pattern
          key={step}
          id={`${idPrefix}-tone-${step}`}
          patternUnits="userSpaceOnUse"
          width={pitch}
          height={pitch}
          patternTransform="rotate(45)"
        >
          {step > 0 ? <circle cx={pitch / 2} cy={pitch / 2} r={toneDotRadius(step)} className="ink-fill" /> : null}
        </pattern>
      ))}
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
          {toneStep !== null && toneStep > 0 ? <path d={d} fill={`url(#${idPrefix}-tone-${toneStep})`} /> : null}
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
