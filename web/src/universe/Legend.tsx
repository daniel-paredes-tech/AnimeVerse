import { useId, type ReactNode } from "react";
import { FRANCHISE_STOCKS, INK, MASTHEAD_RED, PAPER } from "./palette";
import { progressArc } from "./screentone";
import { StarGlyph, ToneDefs } from "./StarGlyph";

const STOCK = FRANCHISE_STOCKS[1];

function Key({ children, width = 34 }: { children: ReactNode; width?: number }) {
  return (
    <svg className="legend__key" viewBox={`${-width / 2} -17 ${width} 34`} width={width} height={34} aria-hidden="true">
      {children}
    </svg>
  );
}

/** How to read the map, drawn with the map's own marks. */
export function Legend() {
  const idPrefix = `legend${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <div className="legend" role="note" aria-label="How to read the map">
      <svg width="0" height="0" className="legend__defs" aria-hidden="true">
        <defs>
          <ToneDefs idPrefix={idPrefix} steps={[10, 16, 20]} />
        </defs>
      </svg>
      <p className="legend__item">
        <Key width={52}>
          <g transform="translate(-16 4)">
            <StarGlyph r={7} stock={STOCK} toneStep={null} idPrefix={idPrefix} />
          </g>
          <g transform="translate(9 0)">
            <StarGlyph r={15} stock={STOCK} toneStep={null} idPrefix={idPrefix} />
          </g>
        </Key>
        <span>
          <strong>Size</strong> popularity
        </span>
      </p>
      <p className="legend__item">
        <Key width={84}>
          {[10, 16, 20].map((step, i) => (
            <g key={step} transform={`translate(${-28 + i * 28} 0)`}>
              <StarGlyph r={14} stock={STOCK} toneStep={step} idPrefix={idPrefix} />
            </g>
          ))}
        </Key>
        <span>
          <strong>Tone</strong> score 5, 8, 10
        </span>
      </p>
      <p className="legend__item">
        <Key>
          <StarGlyph r={14} stock={STOCK} toneStep={null} idPrefix={idPrefix} />
        </Key>
        <span>
          <strong>Untoned</strong> unscored
        </span>
      </p>
      <p className="legend__item">
        <Key>
          <rect x={-17} y={-17} width={34} height={34} fill={`url(#${idPrefix}-tone-20)`} />
          <circle r={13} fill="none" stroke={PAPER} strokeWidth={4} />
          <circle r={13} fill="none" stroke={INK} strokeWidth={1.5} />
          <path d={progressArc(0, 0, 13, 0.4) ?? ""} fill="none" stroke={MASTHEAD_RED} strokeWidth={3} />
          <g>
            <StarGlyph r={9} stock={STOCK} toneStep={16} idPrefix={idPrefix} />
          </g>
        </Key>
        <span>
          <strong>Ring</strong> on your watchlist, red arc for episodes watched
        </span>
      </p>
    </div>
  );
}
