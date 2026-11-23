// The universe map's geometry. Pure functions only: the same data always gives the
// same picture, so the map looks the same on every visit and can be tested.
//
// Stars are placed per franchise on a golden-angle (sunflower) spiral, most popular
// first, so the brightest anime sits in the middle of its constellation. Each star takes
// the first spiral point where it doesn't touch a star already placed. The
// constellations themselves are then placed the same way (largest first) on a spiral
// stretched to the panel's shape, each kept clear of the others by its outer circle.

export interface LayoutAnimeInput {
  id: number;
  popularity: number | null;
  /** Ids of the anime's franchises (usually one; may be none or several). */
  franchiseIds: readonly number[];
}

export interface LayoutFranchiseInput {
  id: number;
  name: string;
}

export interface LayoutOptions {
  /** Target width / height of the whole map (the panel's shape). */
  aspect: number;
  /** Font size of the franchise name plates, in map units. */
  plateFontSize: number;
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PlacedStar {
  animeId: number;
  x: number;
  y: number;
  /** Radius of the sparkle's tips. */
  r: number;
}

export interface Plate {
  /** Centre x of the plate. */
  cx: number;
  /** Top y of the plate. */
  y: number;
  /** Width reserved for the plate (the drawn plate may be narrower). */
  width: number;
  height: number;
  fontSize: number;
}

export interface Constellation {
  /** `f<id>` for a franchise, `none` for anime without a franchise. */
  key: string;
  franchiseId: number | null;
  name: string;
  cx: number;
  cy: number;
  /** Radius of the star cloud around (cx, cy), watchlist rings included. */
  cloudRadius: number;
  /** Radius of the circle that holds the cloud and its plate, plus a margin. */
  outerRadius: number;
  plate: Plate;
  stars: PlacedStar[];
}

/** An anime in more than one franchise sits in one ("home") and points to the others. */
export interface Bridge {
  animeId: number;
  fromKey: string;
  toKey: string;
}

export interface UniverseLayout {
  constellations: Constellation[];
  bridges: Bridge[];
  /** The box that holds every star and plate, with a margin. */
  bounds: Box;
}

export const STAR_MIN_RADIUS = 6;
export const STAR_MAX_RADIUS = 38;
/** Room kept around every star for a watchlist ring, so the layout never depends on the watchlist. */
export const RING_RESERVE = 5;
export const STAR_GAP = 4;
const SPIRAL_STEP = 9;
const CLOUD_PADDING = 8;
const PLATE_GAP = 6;
const CONSTELLATION_MARGIN = 14;
const CENTRE_SPIRAL_STEP = 14;
const BOUNDS_PADDING = 18;
export const NO_FRANCHISE_KEY = "none";
export const NO_FRANCHISE_NAME = "No franchise";

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/** A deterministic number in [0, 1) from an integer (and a salt). */
export function hash01(n: number, salt = 0): number {
  let x = Math.imul(n | 0, 0x9e3779b1) ^ Math.imul(salt | 0, 0x85ebca6b);
  x ^= x >>> 16;
  x = Math.imul(x, 0x7feb352d);
  x ^= x >>> 15;
  x = Math.imul(x, 0x846ca68b);
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

/** Star radius grows with the square root of popularity, so its area is proportional. */
export function starRadius(popularity: number | null, maxPopularity: number): number {
  if (popularity === null || maxPopularity <= 0) return STAR_MIN_RADIUS;
  const share = Math.sqrt(Math.max(0, popularity) / maxPopularity);
  return STAR_MIN_RADIUS + (STAR_MAX_RADIUS - STAR_MIN_RADIUS) * Math.min(1, share);
}

/** A generous estimate of a plate's width: the name in the display face plus the count. */
export function plateWidth(name: string, count: number, fontSize: number): number {
  const nameWidth = name.length * fontSize * 0.66;
  const countWidth = String(count).length * fontSize * 0.62 + fontSize * 0.8;
  return nameWidth + countWidth + fontSize * 1.6;
}

interface Circle {
  x: number;
  y: number;
  r: number;
}

function fits(circles: readonly Circle[], x: number, y: number, r: number, gap: number): boolean {
  for (const c of circles) {
    if (Math.hypot(c.x - x, c.y - y) < c.r + r + gap) return false;
  }
  return true;
}

/** Places circles (in the given order) on a golden-angle spiral without overlaps. */
function spiralPack(
  items: readonly { r: number; seed: number }[],
  step: number,
  gap: number,
  stretch: number,
  jitter: number,
): Circle[] {
  const placed: Circle[] = [];
  let n = 0;
  for (const item of items) {
    const jx = (hash01(item.seed, 1) - 0.5) * step * jitter;
    const jy = (hash01(item.seed, 2) - 0.5) * step * jitter;
    for (;; n += 1) {
      const rho = step * Math.sqrt(n);
      const theta = n * GOLDEN_ANGLE;
      const x = (n === 0 ? 0 : jx) + rho * Math.cos(theta) * stretch;
      const y = (n === 0 ? 0 : jy) + (rho * Math.sin(theta)) / stretch;
      if (fits(placed, x, y, item.r, gap)) {
        placed.push({ x, y, r: item.r });
        n += 1;
        break;
      }
    }
  }
  return placed;
}

function byPopularity(a: LayoutAnimeInput, b: LayoutAnimeInput): number {
  const pa = a.popularity ?? -1;
  const pb = b.popularity ?? -1;
  return pb - pa || a.id - b.id;
}

/** Computes the whole map. Same inputs, same output, always. */
export function layoutUniverse(
  franchises: readonly LayoutFranchiseInput[],
  anime: readonly LayoutAnimeInput[],
  options: LayoutOptions,
): UniverseLayout {
  const known = new Map(franchises.map((f) => [f.id, f]));
  const maxPopularity = anime.reduce((max, a) => Math.max(max, a.popularity ?? 0), 0);

  // Group each anime under its home franchise: the lowest known franchise id.
  const groups = new Map<string, { franchiseId: number | null; name: string; members: LayoutAnimeInput[] }>();
  const bridges: Bridge[] = [];
  for (const f of [...franchises].sort((a, b) => a.id - b.id)) {
    groups.set(`f${f.id}`, { franchiseId: f.id, name: f.name, members: [] });
  }
  for (const a of [...anime].sort((x, y) => x.id - y.id)) {
    const ids = [...new Set(a.franchiseIds)].filter((id) => known.has(id)).sort((x, y) => x - y);
    const home = ids[0];
    const key = home === undefined ? NO_FRANCHISE_KEY : `f${home}`;
    if (!groups.has(key)) groups.set(key, { franchiseId: null, name: NO_FRANCHISE_NAME, members: [] });
    groups.get(key)!.members.push(a);
    for (const other of ids.slice(1)) bridges.push({ animeId: a.id, fromKey: key, toKey: `f${other}` });
  }

  // Lay out each constellation around its own origin.
  const local: Constellation[] = [];
  for (const [key, group] of groups) {
    if (group.members.length === 0) continue;
    const members = [...group.members].sort(byPopularity);
    const radii = members.map((a) => starRadius(a.popularity, maxPopularity));
    const circles = spiralPack(
      members.map((a, i) => ({ r: radii[i]! + RING_RESERVE, seed: a.id })),
      SPIRAL_STEP,
      STAR_GAP,
      1,
      0.8,
    );
    const stars = members.map((a, i) => ({ animeId: a.id, x: circles[i]!.x, y: circles[i]!.y, r: radii[i]! }));
    const cloudRadius = circles.reduce((max, c) => Math.max(max, Math.hypot(c.x, c.y) + c.r), 0) + CLOUD_PADDING;
    const fontSize = options.plateFontSize;
    const plate: Plate = {
      cx: 0,
      y: cloudRadius + PLATE_GAP,
      width: plateWidth(group.name, members.length, fontSize),
      height: fontSize * 2,
      fontSize,
    };
    const outerRadius =
      Math.max(cloudRadius, Math.hypot(plate.width / 2, plate.y + plate.height)) + CONSTELLATION_MARGIN;
    local.push({
      key,
      franchiseId: group.franchiseId,
      name: group.name,
      cx: 0,
      cy: 0,
      cloudRadius,
      outerRadius,
      plate,
      stars,
    });
  }

  // Place the constellations: largest first, near the middle.
  const order = [...local].sort(
    (a, b) =>
      b.outerRadius - a.outerRadius ||
      (a.franchiseId ?? Number.MAX_SAFE_INTEGER) - (b.franchiseId ?? Number.MAX_SAFE_INTEGER),
  );
  const centres = spiralPack(
    order.map((c) => ({ r: c.outerRadius, seed: c.franchiseId ?? 0 })),
    CENTRE_SPIRAL_STEP,
    0,
    Math.sqrt(options.aspect),
    0,
  );
  const placedByKey = new Map(order.map((c, i) => [c.key, centres[i]!]));

  const constellations = local.map((c) => {
    const centre = placedByKey.get(c.key)!;
    return {
      ...c,
      cx: centre.x,
      cy: centre.y,
      plate: { ...c.plate, cx: centre.x, y: centre.y + c.plate.y },
      stars: c.stars.map((s) => ({ ...s, x: s.x + centre.x, y: s.y + centre.y })),
    };
  });

  return { constellations, bridges, bounds: contentBounds(constellations) };
}

function contentBounds(constellations: readonly Constellation[]): Box {
  if (constellations.length === 0) return { x: 0, y: 0, width: 100, height: 100 };
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const c of constellations) {
    const half = Math.max(c.cloudRadius, c.plate.width / 2);
    minX = Math.min(minX, c.cx - half);
    maxX = Math.max(maxX, c.cx + half);
    minY = Math.min(minY, c.cy - c.cloudRadius);
    maxY = Math.max(maxY, c.plate.y + c.plate.height);
  }
  return {
    x: minX - BOUNDS_PADDING,
    y: minY - BOUNDS_PADDING,
    width: maxX - minX + 2 * BOUNDS_PADDING,
    height: maxY - minY + 2 * BOUNDS_PADDING,
  };
}

/** The smallest box with the given aspect (width / height) that holds `box`, centred on it. */
export function fitBox(box: Box, aspect: number): Box {
  if (!(aspect > 0)) return box;
  const current = box.width / box.height;
  if (current > aspect) {
    const height = box.width / aspect;
    return { x: box.x, y: box.y - (height - box.height) / 2, width: box.width, height };
  }
  const width = box.height * aspect;
  return { x: box.x - (width - box.width) / 2, y: box.y, width, height: box.height };
}

/** How far the star cloud reaches when a constellation is zoomed to fill the panel. */
export const ZOOM_HOLE_FACTOR = 1.04;

/**
 * The view box that makes one constellation's star cloud fill a panel of `aspect`. Two
 * thirds of the spare room go before the cloud (left on a wide panel, top on a tall
 * one), which is where the zoomed spread's title sits.
 */
export function zoomBox(c: Constellation, aspect: number): Box {
  const r = c.cloudRadius * ZOOM_HOLE_FACTOR * 1.06;
  const square = { x: c.cx - r, y: c.cy - r, width: 2 * r, height: 2 * r };
  const box = fitBox(square, aspect);
  const spareX = box.width - square.width;
  const spareY = box.height - square.height;
  if (spareX > 0) return { ...box, x: square.x - spareX * 0.85 };
  if (spareY > 0) return { ...box, y: square.y - spareY * 0.85 };
  return box;
}
