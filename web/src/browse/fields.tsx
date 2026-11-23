import { useEffect, useRef, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

/** The ids that tie a control to its label and to the API's messages about it. */
export function fieldIds(name: string) {
  return { control: `filter-${name}`, errors: `filter-${name}-errors` };
}

/** The aria attributes of a control that may carry API errors. */
export function errorAria(name: string, errors: readonly string[] | undefined) {
  return errors && errors.length > 0
    ? { "aria-invalid": true as const, "aria-describedby": fieldIds(name).errors }
    : {};
}

/** The API's validation messages for one field, as a balloon pointing at the control. */
export function FieldErrors({
  name,
  errors,
  tail = "start",
}: {
  name: string;
  errors: readonly string[] | undefined;
  /** Where the balloon's tail points: under a control at the start or at the end of the row. */
  tail?: "start" | "end";
}) {
  if (!errors || errors.length === 0) return null;
  return (
    <div className={`balloon${tail === "end" ? " balloon--end" : ""}`} id={fieldIds(name).errors}>
      {errors.map((message, i) => (
        <p key={i}>{message}</p>
      ))}
    </div>
  );
}

interface FieldProps {
  name: string;
  label: string;
  errors?: readonly string[];
  /** Help text, shown after the API's messages so those sit right under the control. */
  hint?: string;
  children: ReactNode;
}

/** A labelled control with room for the API's messages underneath. */
export function Field({ name, label, errors, hint, children }: FieldProps) {
  return (
    <div className={`field${errors && errors.length > 0 ? " field--invalid" : ""}`}>
      <label className="field__label" htmlFor={fieldIds(name).control}>
        {label}
      </label>
      {children}
      <FieldErrors name={name} errors={errors} />
      {hint ? <p className="field__hint">{hint}</p> : null}
    </div>
  );
}

/** A native select with the world's chevron drawn beside it. */
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className="select">
      <select className={`control${className ? ` ${className}` : ""}`} {...props}>
        {children}
      </select>
      <svg className="select__chevron" viewBox="0 0 12 8" width="12" height="8" aria-hidden="true">
        <path d="M1 1.5 6 6.5 11 1.5" />
      </svg>
    </span>
  );
}

const DEBOUNCE_MS = 450;

interface DebouncedInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> {
  /** The committed value (from the URL). */
  value: string;
  /** Called once typing pauses, or at once on Enter or when the field loses focus. */
  onCommit: (value: string) => void;
}

/**
 * An input that keeps its own text while the user types and commits it after a pause, so
 * the API isn't asked once per keystroke. It follows the committed value when that
 * changes from outside (Back/Forward, "Clear all").
 */
export function DebouncedInput({ value, onCommit, onKeyDown, onBlur, ...props }: DebouncedInputProps) {
  const [text, setText] = useState(value);
  const committed = useRef(value);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (value !== committed.current) {
      committed.current = value;
      setText(value);
    }
  }, [value]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const commit = (next: string) => {
    window.clearTimeout(timer.current);
    if (next === committed.current) return;
    committed.current = next;
    onCommit(next);
  };

  return (
    <input
      className="control"
      {...props}
      value={text}
      onChange={(event) => {
        const next = event.target.value;
        setText(next);
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => commit(next), DEBOUNCE_MS);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") commit(text);
        onKeyDown?.(event);
      }}
      onBlur={(event) => {
        commit(text);
        onBlur?.(event);
      }}
    />
  );
}
