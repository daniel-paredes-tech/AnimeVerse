// Screentone: every tone on the map is ink dots or ink lines on white paper, never a
// grey fill. Pure functions that return SVG path data.
import { hash01, type Box } from "./layout";

/** Distance between the dots of a star's score tone, in map units. */
export const SCORE_TONE_PITCH = 4.6;
/** Coverage of a perfect 10 (dots almost touching, the stock still shows through). */
const MAX_SCORE_COVERAGE = 0.48;

/**
 * A score (0–10) as a tone step: half points, 0..20. `null` stays `null`: an unscored
 * anime is printed untoned, which is different from a score of 0.
 */
export function scoreToneStep(score: number | null): number | null {
  if (score === null || !Number.isFinite(score)) return null;
  return Math.round(Math.min(10, Math.max(0, score)) * 2);
}

/**
 * Dot radius of a tone step, for dots on a square grid of `pitch`. Ink coverage grows
 * linearly with the score: coverage = pi r^2 / pitch^2.
 */
export function toneDotRadius(step: number, pitch = SCORE_TONE_PITCH): number {
  const coverage = (step / 20) * MAX_SCORE_COVERAGE;
  return pitch * Math.sqrt(coverage / Math.PI);
}

const round = (n: number) => Math.round(n * 100) / 100;

function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

export interface SkyClearing {
  cx: number;
  cy: number;
  r: number;
}

/** One sheet of sky tone: dots of one size, laid where the tone is at least `coverage`. */
export interface SkyLevel {
  /** Ink coverage of this sheet's dots (0..1). */
  coverage: number;
  /** The sheet covers the sky from the top down to this y. */
  bottom: number;
  /** Where the sheet is cut away around each constellation. */
  holes: SkyClearing[];
}

const SKY_TOP_COVERAGE = 0.74;
const SKY_BOTTOM_COVERAGE = 0.4;
const SKY_LEVELS = [0.1, 0.18, 0.26, 0.34, 0.42, 0.5, 0.58, 0.66, 0.74];

/** How much of the sky tone is left at distance `d` (in clearing radii) from a centre. */
function clearingFactor(d: number): number {
  return 0.25 + 0.75 * smoothstep(0.5, 1.3, d);
}

/**
 * The night sky as stacked tone sheets, like layers of screentone cut by hand: each
 * level is a dot screen of one size, present where the tone field reaches it. The field
 * is darkest at the top and thins out around every constellation, so the stars sit in a
 * pool of lighter tone. Every sheet uses the same grid, so a larger dot always covers
 * the smaller one beneath it.
 */
export function skyLevels(box: Box, clearings: readonly SkyClearing[]): SkyLevel[] {
  const coverageAt = (y: number) => {
    const t = Math.min(1, Math.max(0, (y - box.y) / box.height));
    return SKY_TOP_COVERAGE + (SKY_BOTTOM_COVERAGE - SKY_TOP_COVERAGE) * t;
  };
  return SKY_LEVELS.map((coverage) => {
    const t = (SKY_TOP_COVERAGE - coverage) / (SKY_TOP_COVERAGE - SKY_BOTTOM_COVERAGE);
    const bottom = t >= 1 ? box.y + box.height : box.y + Math.max(0, t) * box.height;
    const holes: SkyClearing[] = [];
    for (const c of clearings) {
      const needed = coverage / coverageAt(c.cy);
      if (needed <= clearingFactor(0)) continue; // this sheet survives even at the centre
      if (needed >= 1) {
        holes.push({ cx: c.cx, cy: c.cy, r: c.r * 1.3 });
        continue;
      }
      // Find the distance where the clearing lets this sheet back in (bisection).
      let lo = 0;
      let hi = 1.3;
      for (let i = 0; i < 24; i += 1) {
        const mid = (lo + hi) / 2;
        if (clearingFactor(mid) < needed) lo = mid;
        else hi = mid;
      }
      holes.push({ cx: c.cx, cy: c.cy, r: c.r * hi });
    }
    return { coverage, bottom, holes };
  });
}

/** Dot radius for a coverage on a square grid of `pitch`. */
export function dotRadiusForCoverage(coverage: number, pitch: number): number {
  return pitch * Math.sqrt(coverage / Math.PI);
}

/**
 * Manga focus lines around a circle: thin ink wedges that start near the circle's edge
 * (pointed end) and widen outwards past `outer`. Deterministic for a given seed.
 */
export function focusLines(
  cx: number,
  cy: number,
  inner: number,
  outer: number,
  count: number,
  seed: number,
): string {
  const parts: string[] = [];
  for (let i = 0; i < count; i += 1) {
    const a = ((i + hash01(seed + i, 3) * 0.7) / count) * Math.PI * 2;
    const start = inner * (1.03 + hash01(seed + i, 4) * 0.28);
    const half = (0.18 + hash01(seed + i, 5) * 0.55) * (Math.PI / count);
    const x0 = cx + Math.cos(a) * start;
    const y0 = cy + Math.sin(a) * start;
    const x1 = cx + Math.cos(a - half) * outer;
    const y1 = cy + Math.sin(a - half) * outer;
    const x2 = cx + Math.cos(a + half) * outer;
    const y2 = cy + Math.sin(a + half) * outer;
    parts.push(`M${round(x0)} ${round(y0)}L${round(x1)} ${round(y1)}L${round(x2)} ${round(y2)}Z`);
  }
  return parts.join("");
}

/** A four-point sparkle centred on (0, 0) with tips at radius r. */
export function sparklePath(r: number): string {
  const c = r * 0.24;
  const f = (n: number) => round(n);
  return `M0 ${f(-r)}Q${f(c)} ${f(-c)} ${f(r)} 0Q${f(c)} ${f(c)} 0 ${f(r)}Q${f(-c)} ${f(c)} ${f(-r)} 0Q${f(-c)} ${f(-c)} 0 ${f(-r)}Z`;
}

/**
 * The arc of a watching progress ring, clockwise from the top, as a fraction 0..1.
 * Returns `null` for a full circle (draw a circle instead) or nothing to draw.
 */
export function progressArc(cx: number, cy: number, r: number, fraction: number): string | null {
  const f = Math.min(1, Math.max(0, fraction));
  if (f <= 0 || f >= 1) return null;
  const angle = f * Math.PI * 2 - Math.PI / 2;
  const x = cx + Math.cos(angle) * r;
  const y = cy + Math.sin(angle) * r;
  const large = f > 0.5 ? 1 : 0;
  return `M${round(cx)} ${round(cy - r)}A${round(r)} ${round(r)} 0 ${large} 1 ${round(x)} ${round(y)}`;
}
