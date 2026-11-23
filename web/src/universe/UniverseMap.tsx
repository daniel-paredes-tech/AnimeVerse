import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { Link, useNavigate } from "react-router";
import type { AnimeSummary } from "../api/types";
import { starAccessibleName } from "../lib/labels";
import { useElementSize, usePrefersReducedMotion } from "../lib/useMedia";
import {
  NO_FRANCHISE_KEY,
  RING_RESERVE,
  ZOOM_HOLE_FACTOR,
  fitBox,
  layoutUniverse,
  zoomBox,
  type Box,
  type Constellation,
} from "./layout";
import type { UniverseFilters, UniverseFranchise } from "./model";
import { matchesFilters } from "./model";
import { PAPER, stockByFranchiseId } from "./palette";
import { dotRadiusForCoverage, focusLines, scoreToneStep, skyLevels } from "./screentone";
import { StarCard, type CardAnchor } from "./StarCard";
import { StarGlyph, ToneDefs } from "./StarGlyph";

const PRESETS = {
  wide: { aspect: 1.55, plateFontSize: 22 },
  tall: { aspect: 0.8, plateFontSize: 30 },
} as const;
const SKY_DOT_PITCH_PX = 6;

const ZOOM_MS = 760;
const CARD_HIDE_DELAY = 140;

interface UniverseMapProps {
  anime: readonly AnimeSummary[];
  franchises: readonly UniverseFranchise[];
  filters: UniverseFilters;
  shape: keyof typeof PRESETS;
}

const boxString = (b: Box) => `${b.x.toFixed(2)} ${b.y.toFixed(2)} ${b.width.toFixed(2)} ${b.height.toFixed(2)}`;
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerpBox = (a: Box, b: Box, t: number): Box => ({
  x: lerp(a.x, b.x, t),
  y: lerp(a.y, b.y, t),
  width: lerp(a.width, b.width, t),
  height: lerp(a.height, b.height, t),
});
/** Exponential ease-out: fast start, long soft landing. */
const easeOutExpo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

export function UniverseMap({ anime, franchises, filters, shape }: UniverseMapProps) {
  const idPrefix = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const navigate = useNavigate();
  const reducedMotion = usePrefersReducedMotion();
  const panelRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const size = useElementSize(panelRef);
  const preset = PRESETS[shape];

  // --- Geometry (pure, memoised) ------------------------------------------------------
  const layout = useMemo(
    () =>
      layoutUniverse(
        franchises.map((f) => ({ id: f.id, name: f.name })),
        anime.map((a) => ({ id: a.id, popularity: a.popularity, franchiseIds: a.franchises.map((f) => f.id) })),
        preset,
      ),
    [anime, franchises, preset],
  );
  const byId = useMemo(() => new Map(anime.map((a) => [a.id, a])), [anime]);
  const stocks = useMemo(() => stockByFranchiseId(franchises.map((f) => f.id)), [franchises]);
  const counts = useMemo(() => new Map(franchises.map((f) => [f.id, f.animeCount])), [franchises]);
  const aspect = size ? size.width / size.height : preset.aspect;
  const baseBox = useMemo(() => fitBox(layout.bounds, aspect), [layout, aspect]);

  const [card, setCard] = useState<{ anime: AnimeSummary; anchor: CardAnchor } | null>(null);
  const hideTimer = useRef<number | undefined>(undefined);

  // --- Zoom ----------------------------------------------------------------------------
  const [zoomKey, setZoomKey] = useState<string | null>(null);
  const focused = layout.constellations.find((c) => c.key === zoomKey) ?? null;
  const targetBox = focused ? zoomBox(focused, aspect) : baseBox;
  const targetString = boxString(targetBox);
  const shownBox = useRef<Box | null>(null);
  const animateNext = useRef(false);
  const backRef = useRef<HTMLButtonElement>(null);
  const returnFocusTo = useRef<HTMLElement | SVGElement | null>(null);
  const [announcement, setAnnouncement] = useState("");

  useLayoutEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const from = shownBox.current;
    const to = targetBox;
    const animate = animateNext.current && from !== null && !reducedMotion;
    animateNext.current = false;
    if (!animate) {
      svg.setAttribute("viewBox", boxString(to));
      shownBox.current = to;
      return;
    }
    svg.setAttribute("viewBox", boxString(from));
    const start = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const t = Math.min(1, (now - start) / ZOOM_MS);
      const box = lerpBox(from, to, easeOutExpo(t));
      svg.setAttribute("viewBox", boxString(box));
      shownBox.current = box;
      if (t < 1) frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
    // targetString stands for targetBox (a new object on every render).
  }, [targetString, reducedMotion]);

  const zoomTo = useCallback(
    (c: Constellation) => {
      animateNext.current = true;
      const active = document.activeElement;
      returnFocusTo.current = active instanceof HTMLElement || active instanceof SVGElement ? active : null;
      setCard(null);
      setZoomKey(c.key);
      setAnnouncement(`${c.name}: ${c.stars.length} anime fill the panel. Press Escape to go back to the universe.`);
    },
    [],
  );

  const zoomOut = useCallback(() => {
    animateNext.current = true;
    setCard(null);
    setZoomKey(null);
    setAnnouncement("Back to the whole universe.");
  }, []);

  // Focus follows the zoom: into the "back" control, then back to what opened it.
  useEffect(() => {
    if (zoomKey !== null) {
      backRef.current?.focus();
    } else if (returnFocusTo.current) {
      returnFocusTo.current.focus();
      returnFocusTo.current = null;
    }
  }, [zoomKey]);

  // --- Hover / focus card --------------------------------------------------------------
  const cancelHide = () => window.clearTimeout(hideTimer.current);
  const scheduleHide = () => {
    cancelHide();
    hideTimer.current = window.setTimeout(() => setCard(null), CARD_HIDE_DELAY);
  };
  useEffect(() => () => window.clearTimeout(hideTimer.current), []);

  const showCard = (event: MouseEvent<Element> | FocusEvent<Element>, a: AnimeSummary) => {
    const panel = panelRef.current;
    if (!panel) return;
    cancelHide();
    const star = event.currentTarget.getBoundingClientRect();
    const box = panel.getBoundingClientRect();
    setCard({
      anime: a,
      anchor: {
        x: star.left + star.width / 2 - box.left,
        y: star.top + star.height / 2 - box.top,
        r: Math.min(star.width, star.height) / 2,
      },
    });
  };

  // Esc closes the card first, then zooms out.
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (card) {
        setCard(null);
      } else if (zoomKey !== null) {
        event.preventDefault();
        zoomOut();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, zoomKey, zoomOut]);

  const openAnime = (event: MouseEvent<Element>, id: number) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    navigate(`/anime/${id}`);
  };

  // --- Static layers (memoised so hover re-renders skip them) --------------------------
  // The sky: stacked dot screens, about 6 px apart on screen whatever the panel size.
  const panelWidth = size?.width ?? null;
  const sky = useMemo(() => {
    const pad = Math.max(baseBox.width, baseBox.height) * 0.1;
    const box = { x: baseBox.x - pad, y: baseBox.y - pad, width: baseBox.width + 2 * pad, height: baseBox.height + 2 * pad };
    const pitch = panelWidth ? (baseBox.width * SKY_DOT_PITCH_PX) / panelWidth : baseBox.width / 200;
    const clearings = layout.constellations.map((c) => ({ cx: c.cx, cy: c.cy, r: c.cloudRadius * 1.1 }));
    const levels = skyLevels(box, clearings);
    const id = (i: number, kind: string) => `${idPrefix}-sky-${kind}-${i}`;
    return (
      <g className="sky" aria-hidden="true">
        <defs>
          {levels.map((level, i) => (
            <pattern
              key={i}
              id={id(i, "dots")}
              patternUnits="userSpaceOnUse"
              width={pitch}
              height={pitch}
              patternTransform="rotate(45)"
            >
              <circle cx={pitch / 2} cy={pitch / 2} r={dotRadiusForCoverage(level.coverage, pitch)} />
            </pattern>
          ))}
          {levels.map((level, i) => (
            <mask key={i} id={id(i, "cut")} maskUnits="userSpaceOnUse" x={box.x} y={box.y} width={box.width} height={box.height}>
              <rect x={box.x} y={box.y} width={box.width} height={level.bottom - box.y} fill="#fff" />
              {level.holes.map((h, j) => (
                <circle key={j} cx={h.cx} cy={h.cy} r={h.r} fill="#000" />
              ))}
            </mask>
          ))}
        </defs>
        {levels.map((_, i) => (
          <rect
            key={i}
            x={box.x}
            y={box.y}
            width={box.width}
            height={box.height}
            fill={`url(#${id(i, "dots")})`}
            mask={`url(#${id(i, "cut")})`}
          />
        ))}
      </g>
    );
  }, [baseBox, layout, panelWidth, idPrefix]);

  const bridges = useMemo(() => {
    const centres = new Map(layout.constellations.map((c) => [c.key, c]));
    const starAt = new Map(layout.constellations.flatMap((c) => c.stars.map((s) => [s.animeId, s] as const)));
    return layout.bridges.map((b) => {
      const s = starAt.get(b.animeId);
      const to = centres.get(b.toKey);
      if (!s || !to) return null;
      return (
        <line
          key={`${b.animeId}-${b.toKey}`}
          x1={s.x}
          y1={s.y}
          x2={to.cx}
          y2={to.cy}
          className="bridge"
          stroke={PAPER}
        />
      );
    });
  }, [layout]);

  const zoomOverlay = focused ? <ZoomBurst c={focused} base={baseBox} aspect={aspect} /> : null;
  const focusedCount = focused ? (focused.franchiseId !== null ? counts.get(focused.franchiseId) : undefined) ?? focused.stars.length : 0;
  const focusedOnList = focused ? focused.stars.filter((s) => byId.get(s.animeId)?.watchlist_entry).length : 0;

  return (
    <>
    <div className={`sky-panel${focused ? " sky-panel--zoomed" : ""}`} ref={panelRef}>
      <svg
        ref={svgRef}
        className="sky-panel__svg"
        viewBox={targetString}
        preserveAspectRatio="xMidYMid meet"
        role="group"
        aria-label={`Universe map: ${layout.constellations.length} franchise constellations, ${anime.length} anime. Each star is a link.`}
      >
        <defs>
          <ToneDefs idPrefix={idPrefix} />
        </defs>
        <rect
          x={baseBox.x - baseBox.width}
          y={baseBox.y - baseBox.height}
          width={baseBox.width * 3}
          height={baseBox.height * 3}
          fill={PAPER}
        />
        {sky}
        {bridges}
        {layout.constellations.map((c) => {
          const hidden = focused !== null && focused.key !== c.key;
          const stock = c.franchiseId !== null ? stocks.get(c.franchiseId) ?? PAPER : PAPER;
          return (
            <g key={c.key} className="constellation" aria-hidden={hidden || undefined}>
              {c.stars.map((s) => {
                const a = byId.get(s.animeId);
                if (!a) return null;
                const dim = !matchesFilters(a, filters);
                return (
                  <a
                    key={s.animeId}
                    href={`/anime/${a.id}`}
                    className={`star${dim ? " star--dim" : ""}`}
                    aria-label={starAccessibleName(a, dim)}
                    tabIndex={hidden ? -1 : 0}
                    onClick={(e) => openAnime(e, a.id)}
                    onMouseEnter={(e) => showCard(e, a)}
                    onMouseLeave={scheduleHide}
                    onFocus={(e) => showCard(e, a)}
                    onBlur={() => setCard(null)}
                  >
                    <g transform={`translate(${s.x.toFixed(2)} ${s.y.toFixed(2)})`}>
                      <circle r={s.r + RING_RESERVE} className="star__hit" />
                      <StarGlyph
                        r={s.r}
                        stock={stock}
                        toneStep={scoreToneStep(a.score)}
                        idPrefix={idPrefix}
                        dim={dim}
                        entry={a.watchlist_entry}
                        episodes={a.episodes}
                      />
                      <circle r={s.r + RING_RESERVE + 1} className="star__focus" />
                    </g>
                  </a>
                );
              })}
            </g>
          );
        })}
        {zoomOverlay}
        {layout.constellations.map((c) => (
          <PlateButton
            key={c.key}
            c={c}
            count={(c.franchiseId !== null ? counts.get(c.franchiseId) : undefined) ?? c.stars.length}
            stock={c.franchiseId !== null ? stocks.get(c.franchiseId) ?? PAPER : PAPER}
            hidden={focused !== null}
            pointerOnly={shape === "tall"}
            onZoom={zoomTo}
          />
        ))}
      </svg>

      {focused ? (
        <div className="zoom-head">
          <h2 className="zoom-head__title">{focused.name}</h2>
          <p className="zoom-head__meta">
            {focusedCount} anime · {focusedOnList === 0 ? "none" : focusedOnList} on your watchlist
          </p>
          <div className="zoom-head__actions">
            <button ref={backRef} type="button" className="button button--ink" onClick={zoomOut}>
              Back to the universe
            </button>
            {focused.key !== NO_FRANCHISE_KEY && focused.franchiseId !== null ? (
              <Link className="button" to={`/anime?franchise=${focused.franchiseId}`}>
                List this franchise
              </Link>
            ) : null}
          </div>
          <p className="zoom-head__hint">Esc also goes back.</p>
        </div>
      ) : null}

      {card && size ? (
        <StarCard
          anime={card.anime}
          anchor={card.anchor}
          panel={size}
          onPointerEnter={cancelHide}
          onPointerLeave={scheduleHide}
          onOpen={() => navigate(`/anime/${card.anime.id}`)}
        />
      ) : null}

      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </div>
    {shape === "tall" ? (
      <ul className="plate-strip" aria-label="Franchises">
        {layout.constellations.map((c) => {
          const count = (c.franchiseId !== null ? counts.get(c.franchiseId) : undefined) ?? c.stars.length;
          return (
            <li key={c.key}>
              <button
                type="button"
                className="plate-chip"
                style={{ backgroundColor: c.franchiseId !== null ? stocks.get(c.franchiseId) ?? PAPER : PAPER }}
                aria-pressed={focused?.key === c.key}
                aria-label={`${c.name}: ${count} anime. Zoom into this constellation`}
                onClick={() => (focused?.key === c.key ? zoomOut() : zoomTo(c))}
              >
                <span className="plate-chip__name">{c.name}</span>
                <span className="plate-chip__count">{count}</span>
              </button>
            </li>
          );
        })}
      </ul>
    ) : null}
    </>
  );
}

/** A franchise name plate: a button drawn in SVG. Activating it zooms the constellation. */
function PlateButton({
  c,
  count,
  stock,
  hidden,
  pointerOnly,
  onZoom,
}: {
  c: Constellation;
  count: number;
  stock: string;
  hidden: boolean;
  /** On narrow panels the plate strip below the map is the accessible control. */
  pointerOnly: boolean;
  onZoom: (c: Constellation) => void;
}) {
  const textRef = useRef<SVGTextElement>(null);
  const [nameWidth, setNameWidth] = useState<number | null>(null);
  const { fontSize, height } = c.plate;

  useLayoutEffect(() => {
    const text = textRef.current;
    if (text && typeof text.getComputedTextLength === "function") {
      const width = text.getComputedTextLength();
      if (width > 0) setNameWidth(width);
    }
  }, [c.name, fontSize]);

  // Re-measure once the display face has loaded (the fallback is narrower or wider).
  useEffect(() => {
    if (typeof document === "undefined" || !document.fonts) return;
    let alive = true;
    void document.fonts.ready.then(() => {
      const text = textRef.current;
      if (alive && text && typeof text.getComputedTextLength === "function") {
        const width = text.getComputedTextLength();
        if (width > 0) setNameWidth(width);
      }
    });
    return () => {
      alive = false;
    };
  }, [c.name, fontSize]);

  const padX = fontSize * 0.7;
  const countBox = fontSize * (0.9 + String(count).length * 0.62);
  const nameW = nameWidth ?? c.plate.width - countBox - 2 * padX;
  const width = Math.min(c.plate.width, nameW + 2 * padX + countBox);
  const x = c.plate.cx - width / 2;
  const y = c.plate.y;
  const baseline = y + height / 2 + fontSize * 0.36;

  const activate = () => onZoom(c);
  const onKeyDown = (event: KeyboardEvent<SVGGElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate();
    }
  };

  return (
    <g
      className="plate"
      role={pointerOnly ? undefined : "button"}
      tabIndex={hidden || pointerOnly ? -1 : 0}
      aria-hidden={hidden || pointerOnly || undefined}
      aria-label={`${c.name}: ${count} anime. Zoom into this constellation`}
      visibility={hidden ? "hidden" : undefined}
      onClick={activate}
      onKeyDown={onKeyDown}
    >
      <rect x={x} y={y} width={width} height={height} fill={stock} className="plate__box" />
      <text ref={textRef} x={x + padX} y={baseline} className="plate__name" fontSize={fontSize}>
        {c.name}
      </text>
      <rect x={x + width - countBox} y={y} width={countBox} height={height} className="plate__count-box" />
      <text
        x={x + width - countBox / 2}
        y={baseline}
        className="plate__count"
        fontSize={fontSize * 0.92}
        textAnchor="middle"
      >
        {count}
      </text>
      <rect x={x - 4} y={y - 4} width={width + 8} height={height + 8} className="plate__focus" />
    </g>
  );
}

/**
 * The zoomed spread: paper covers everything outside the constellation's clearing, and
 * focus lines burst in towards it. Drawn in map units, so it zooms with the view box.
 */
export function ZoomBurst({ c, base, aspect }: { c: Constellation; base: Box; aspect: number }) {
  const zoom = zoomBox(c, aspect);
  const r = c.cloudRadius * ZOOM_HOLE_FACTOR;
  const minX = Math.min(base.x, zoom.x) - base.width;
  const minY = Math.min(base.y, zoom.y) - base.height;
  const maxX = Math.max(base.x + base.width, zoom.x + zoom.width) + base.width;
  const maxY = Math.max(base.y + base.height, zoom.y + zoom.height) + base.height;
  const field =
    `M${minX} ${minY}H${maxX}V${maxY}H${minX}Z` +
    `M${c.cx - r} ${c.cy}A${r} ${r} 0 1 0 ${c.cx + r} ${c.cy}A${r} ${r} 0 1 0 ${c.cx - r} ${c.cy}Z`;
  const outer = Math.hypot(zoom.width, zoom.height);
  const lines = focusLines(c.cx, c.cy, r, outer, 120, c.franchiseId ?? 0);
  return (
    <g
      key={c.key}
      className="burst"
      style={{ transformOrigin: `${c.cx}px ${c.cy}px`, transformBox: "view-box" }}
      aria-hidden="true"
    >
      <path d={field} fillRule="evenodd" fill={PAPER} />
      <path d={lines} className="ink-fill burst__lines" />
      <circle cx={c.cx} cy={c.cy} r={r} className="burst__frame" />
    </g>
  );
}
