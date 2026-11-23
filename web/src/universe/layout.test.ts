import { describe, expect, it } from "vitest";
import {
  NO_FRANCHISE_KEY,
  RING_RESERVE,
  STAR_MAX_RADIUS,
  STAR_MIN_RADIUS,
  ZOOM_HOLE_FACTOR,
  fitBox,
  hash01,
  layoutUniverse,
  starRadius,
  zoomBox,
  type LayoutAnimeInput,
  type LayoutFranchiseInput,
  type UniverseLayout,
} from "./layout";
import { scoreToneStep, toneDotRadius } from "./screentone";

// The real catalogue's shape: 7 franchises, 163 anime (PRODUCT.md).
const FRANCHISES: LayoutFranchiseInput[] = [
  { id: 6, name: "Attack on Titan" },
  { id: 7, name: "Demon Slayer" },
  { id: 5, name: "Dragon Ball" },
  { id: 2, name: "Jujutsu Kaisen" },
  { id: 1, name: "Naruto" },
  { id: 4, name: "One Piece" },
  { id: 3, name: "Yu-Gi-Oh!" },
];
const COUNTS: Record<number, number> = { 1: 26, 2: 10, 3: 21, 4: 39, 5: 38, 6: 20, 7: 9 };

function catalogue(): LayoutAnimeInput[] {
  const anime: LayoutAnimeInput[] = [];
  let id = 1;
  for (const [franchise, count] of Object.entries(COUNTS)) {
    for (let i = 0; i < count; i += 1) {
      const roll = hash01(id, 9);
      anime.push({
        id,
        // 291 .. 1 081 173 like the real data, with one unknown popularity.
        popularity: id === 17 ? null : Math.round(291 + roll ** 3 * 1_080_882),
        franchiseIds: [Number(franchise)],
      });
      id += 1;
    }
  }
  return anime;
}

const OPTIONS = { aspect: 1.55, plateFontSize: 17 };

function allStars(layout: UniverseLayout) {
  return layout.constellations.flatMap((c) => c.stars.map((s) => ({ ...s, key: c.key })));
}

describe("layoutUniverse", () => {
  it("is deterministic: same data, same picture", () => {
    const a = layoutUniverse(FRANCHISES, catalogue(), OPTIONS);
    const b = layoutUniverse([...FRANCHISES].reverse(), [...catalogue()].reverse(), OPTIONS);
    expect(b).toEqual(a);
  });

  it("places every anime exactly once", () => {
    const anime = catalogue();
    const layout = layoutUniverse(FRANCHISES, anime, OPTIONS);
    const placed = allStars(layout).map((s) => s.animeId).sort((x, y) => x - y);
    expect(placed).toEqual(anime.map((a) => a.id).sort((x, y) => x - y));
    for (const s of allStars(layout)) {
      expect(Number.isFinite(s.x) && Number.isFinite(s.y) && Number.isFinite(s.r)).toBe(true);
    }
  });

  it("puts each anime in its franchise's constellation, the most popular in the middle", () => {
    const anime = catalogue();
    const layout = layoutUniverse(FRANCHISES, anime, OPTIONS);
    expect(layout.constellations).toHaveLength(7);
    for (const c of layout.constellations) {
      const members = anime.filter((a) => a.franchiseIds.includes(c.franchiseId!));
      expect(c.stars).toHaveLength(members.length);
      const top = [...members].sort((x, y) => (y.popularity ?? -1) - (x.popularity ?? -1))[0]!;
      expect(c.stars[0]!.animeId).toBe(top.id);
      expect(c.stars[0]!.x).toBeCloseTo(c.cx);
      expect(c.stars[0]!.y).toBeCloseTo(c.cy);
    }
  });

  it("never lets two stars of a constellation overlap (rings included)", () => {
    const layout = layoutUniverse(FRANCHISES, catalogue(), OPTIONS);
    for (const c of layout.constellations) {
      for (let i = 0; i < c.stars.length; i += 1) {
        for (let j = i + 1; j < c.stars.length; j += 1) {
          const a = c.stars[i]!;
          const b = c.stars[j]!;
          const distance = Math.hypot(a.x - b.x, a.y - b.y);
          expect(distance).toBeGreaterThanOrEqual(a.r + b.r + 2 * RING_RESERVE);
        }
      }
    }
  });

  it("keeps constellations apart: outer circles never overlap", () => {
    const layout = layoutUniverse(FRANCHISES, catalogue(), OPTIONS);
    const cs = layout.constellations;
    for (let i = 0; i < cs.length; i += 1) {
      for (let j = i + 1; j < cs.length; j += 1) {
        const a = cs[i]!;
        const b = cs[j]!;
        expect(Math.hypot(a.cx - b.cx, a.cy - b.cy)).toBeGreaterThanOrEqual(a.outerRadius + b.outerRadius - 1e-9);
      }
    }
  });

  it("keeps every star and plate inside its own outer circle and inside the bounds", () => {
    const layout = layoutUniverse(FRANCHISES, catalogue(), OPTIONS);
    const { bounds } = layout;
    for (const c of layout.constellations) {
      for (const s of c.stars) {
        expect(Math.hypot(s.x - c.cx, s.y - c.cy) + s.r + RING_RESERVE).toBeLessThanOrEqual(c.cloudRadius);
        expect(s.x - s.r).toBeGreaterThanOrEqual(bounds.x);
        expect(s.x + s.r).toBeLessThanOrEqual(bounds.x + bounds.width);
        expect(s.y - s.r).toBeGreaterThanOrEqual(bounds.y);
        expect(s.y + s.r).toBeLessThanOrEqual(bounds.y + bounds.height);
      }
      const p = c.plate;
      const corner = Math.hypot(p.width / 2, p.y + p.height - c.cy);
      expect(corner).toBeLessThanOrEqual(c.outerRadius);
      expect(p.y + p.height).toBeLessThanOrEqual(bounds.y + bounds.height);
    }
  });

  it("keeps a zoomed constellation's clearing free of every other constellation", () => {
    const layout = layoutUniverse(FRANCHISES, catalogue(), OPTIONS);
    for (const c of layout.constellations) {
      const hole = c.cloudRadius * ZOOM_HOLE_FACTOR;
      for (const other of layout.constellations) {
        if (other === c) continue;
        expect(Math.hypot(c.cx - other.cx, c.cy - other.cy)).toBeGreaterThanOrEqual(hole + other.outerRadius);
      }
    }
  });

  it("follows the panel's shape", () => {
    const wide = layoutUniverse(FRANCHISES, catalogue(), { aspect: 1.6, plateFontSize: 17 }).bounds;
    const tall = layoutUniverse(FRANCHISES, catalogue(), { aspect: 0.7, plateFontSize: 28 }).bounds;
    expect(wide.width / wide.height).toBeGreaterThan(tall.width / tall.height);
  });

  it("puts anime without a franchise in their own constellation", () => {
    const anime = [...catalogue(), { id: 999, popularity: 500, franchiseIds: [] }];
    const layout = layoutUniverse(FRANCHISES, anime, OPTIONS);
    const none = layout.constellations.find((c) => c.key === NO_FRANCHISE_KEY);
    expect(none?.stars.map((s) => s.animeId)).toEqual([999]);
    expect(none?.franchiseId).toBeNull();
  });

  it("draws an anime of two franchises once, in the lower id, with a bridge to the other", () => {
    const anime = [...catalogue(), { id: 1000, popularity: 9000, franchiseIds: [5, 2] }];
    const layout = layoutUniverse(FRANCHISES, anime, OPTIONS);
    const homes = allStars(layout).filter((s) => s.animeId === 1000);
    expect(homes).toHaveLength(1);
    expect(homes[0]!.key).toBe("f2");
    expect(layout.bridges).toEqual([{ animeId: 1000, fromKey: "f2", toKey: "f5" }]);
  });

  it("handles an empty catalogue", () => {
    const layout = layoutUniverse(FRANCHISES, [], OPTIONS);
    expect(layout.constellations).toEqual([]);
    expect(layout.bounds.width).toBeGreaterThan(0);
  });
});

describe("starRadius", () => {
  it("grows with the square root of popularity", () => {
    expect(starRadius(1_000_000, 1_000_000)).toBe(STAR_MAX_RADIUS);
    expect(starRadius(0, 1_000_000)).toBe(STAR_MIN_RADIUS);
    const quarter = starRadius(250_000, 1_000_000);
    expect(quarter).toBeCloseTo(STAR_MIN_RADIUS + (STAR_MAX_RADIUS - STAR_MIN_RADIUS) / 2);
  });

  it("draws an unknown popularity at the smallest size", () => {
    expect(starRadius(null, 1_000_000)).toBe(STAR_MIN_RADIUS);
  });
});

describe("fitBox and zoomBox", () => {
  it("grows a box to the panel's shape without cutting it", () => {
    const box = { x: 0, y: 0, width: 200, height: 100 };
    expect(fitBox(box, 1)).toEqual({ x: 0, y: -50, width: 200, height: 200 });
    expect(fitBox(box, 4)).toEqual({ x: -100, y: 0, width: 400, height: 100 });
  });

  it("fits a zoomed cloud in the panel, with the spare room mostly before it", () => {
    const layout = layoutUniverse(FRANCHISES, catalogue(), OPTIONS);
    const c = layout.constellations[0]!;
    for (const aspect of [1.5, 0.8]) {
      const box = zoomBox(c, aspect);
      expect(box.width / box.height).toBeCloseTo(aspect);
      expect(c.cx - c.cloudRadius).toBeGreaterThanOrEqual(box.x);
      expect(c.cx + c.cloudRadius).toBeLessThanOrEqual(box.x + box.width);
      expect(c.cy - c.cloudRadius).toBeGreaterThanOrEqual(box.y);
      expect(c.cy + c.cloudRadius).toBeLessThanOrEqual(box.y + box.height);
      const before = aspect > 1 ? c.cx - box.x : c.cy - box.y;
      const after = aspect > 1 ? box.x + box.width - c.cx : box.y + box.height - c.cy;
      expect(before).toBeGreaterThan(after);
    }
  });
});

describe("score tone", () => {
  it("keeps unscored anime untoned, unlike a score of zero", () => {
    expect(scoreToneStep(null)).toBeNull();
    expect(scoreToneStep(0)).toBe(0);
    expect(toneDotRadius(0)).toBe(0);
  });

  it("gets denser with the score, in half-point steps", () => {
    expect(scoreToneStep(8.24)).toBe(16);
    expect(scoreToneStep(8.26)).toBe(17);
    expect(toneDotRadius(17)).toBeGreaterThan(toneDotRadius(10));
  });
});
