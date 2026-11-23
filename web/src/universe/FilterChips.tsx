import { useId, type ReactNode } from "react";
import type { FilterOption } from "./model";

/** A labelled row of toggle buttons. */
export function ChipRow({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  const id = useId();
  return (
    <div className={`chips${className ? ` ${className}` : ""}`} role="group" aria-labelledby={id}>
      <span className="chips__label" id={id}>
        {label}
      </span>
      <div className="chips__row">{children}</div>
    </div>
  );
}

interface ChipGroupProps {
  label: string;
  options: readonly FilterOption[];
  value: string | null;
  onChange: (value: string | null) => void;
}

/** Filter chips: one value at a time, or "All". */
export function ChipGroup({ label, options, value, onChange }: ChipGroupProps) {
  return (
    <ChipRow label={label}>
      <button type="button" className="chip" aria-pressed={value === null} onClick={() => onChange(null)}>
        All
      </button>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className="chip"
          aria-pressed={value === option.value}
          onClick={() => onChange(value === option.value ? null : option.value)}
        >
          {option.label} <span className="chip__count">{option.count}</span>
        </button>
      ))}
    </ChipRow>
  );
}
