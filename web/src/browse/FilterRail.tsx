import type { AnimeListQuery, Franchise } from "../api/types";
import { formatLabel, releaseStatusLabel, watchStatusLabel } from "../lib/labels";
import { DebouncedInput, Field, FieldErrors, Select, errorAria, fieldIds } from "./fields";
import { FORMATS, RELEASE_STATUSES, WATCH_STATUSES, activeFilters, type FilterParam } from "./query";

export type FieldErrorMap = Partial<Record<string, string[]>>;

interface FilterRailProps {
  query: AnimeListQuery;
  franchises: readonly Franchise[] | undefined;
  errors: FieldErrorMap;
  onChange: <K extends FilterParam>(key: K, value: AnimeListQuery[K] | undefined) => void;
  onClearAll: () => void;
}

function toNumber(text: string): number | undefined {
  if (text.trim() === "") return undefined;
  const n = Number(text);
  return Number.isFinite(n) ? n : undefined;
}

/** Every filter of `GET /v1/anime`, as standard controls. */
export function FilterRail({ query, franchises, errors, onChange, onClearAll }: FilterRailProps) {
  const active = activeFilters(query).length;
  const knownFranchise = franchises?.some((f) => f.id === query.franchise) ?? true;

  return (
    <form className="filters" aria-labelledby="filters-title" role="search" onSubmit={(e) => e.preventDefault()}>
      <div className="filters__head">
        <h2 id="filters-title" className="filters__title">
          Filters
        </h2>
        {active > 0 ? (
          <button type="button" className="link-button" onClick={onClearAll}>
            Clear all ({active})
          </button>
        ) : null}
      </div>

      <Field name="q" label="Title contains" errors={errors.q}>
        <DebouncedInput
          id={fieldIds("q").control}
          type="search"
          value={query.q ?? ""}
          maxLength={100}
          autoComplete="off"
          spellCheck={false}
          placeholder="Any title, any language"
          onCommit={(text) => onChange("q", text.trim() === "" ? undefined : text)}
          {...errorAria("q", errors.q)}
        />
      </Field>

      <Field name="franchise" label="Franchise" errors={errors.franchise}>
        <Select
          id={fieldIds("franchise").control}
          value={query.franchise ?? ""}
          onChange={(e) => onChange("franchise", e.target.value === "" ? undefined : Number(e.target.value))}
          {...errorAria("franchise", errors.franchise)}
        >
          <option value="">Any franchise</option>
          {franchises?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} ({f.anime_count})
            </option>
          ))}
          {query.franchise !== undefined && !knownFranchise ? (
            <option value={query.franchise}>Franchise {query.franchise} (not in the list)</option>
          ) : null}
        </Select>
      </Field>

      <Field name="status" label="Release status" errors={errors.status}>
        <Select
          id={fieldIds("status").control}
          value={query.status ?? ""}
          onChange={(e) =>
            onChange("status", e.target.value === "" ? undefined : (e.target.value as AnimeListQuery["status"]))
          }
          {...errorAria("status", errors.status)}
        >
          <option value="">Any release status</option>
          {RELEASE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {releaseStatusLabel(s)}
            </option>
          ))}
        </Select>
      </Field>

      <Field name="format" label="Format" errors={errors.format}>
        <Select
          id={fieldIds("format").control}
          value={query.format ?? ""}
          onChange={(e) =>
            onChange("format", e.target.value === "" ? undefined : (e.target.value as AnimeListQuery["format"]))
          }
          {...errorAria("format", errors.format)}
        >
          <option value="">Any format</option>
          {FORMATS.map((f) => (
            <option key={f} value={f}>
              {formatLabel(f)}
            </option>
          ))}
        </Select>
      </Field>

      <fieldset
        className={`field field--pair${errors.year_from?.length || errors.year_to?.length ? " field--invalid" : ""}`}
      >
        <legend className="field__label">Started between</legend>
        <div className="pair">
          <label className="pair__label" htmlFor={fieldIds("year_from").control}>
            From
          </label>
          <DebouncedInput
            id={fieldIds("year_from").control}
            type="number"
            inputMode="numeric"
            min={1900}
            max={2100}
            step={1}
            value={query.year_from === undefined ? "" : String(query.year_from)}
            onCommit={(text) => onChange("year_from", toNumber(text))}
            {...errorAria("year_from", errors.year_from)}
          />
          <label className="pair__label" htmlFor={fieldIds("year_to").control}>
            to
          </label>
          <DebouncedInput
            id={fieldIds("year_to").control}
            type="number"
            inputMode="numeric"
            min={1900}
            max={2100}
            step={1}
            value={query.year_to === undefined ? "" : String(query.year_to)}
            onCommit={(text) => onChange("year_to", toNumber(text))}
            {...errorAria("year_to", errors.year_to)}
          />
        </div>
        <FieldErrors name="year_from" errors={errors.year_from} />
        <FieldErrors name="year_to" errors={errors.year_to} tail="end" />
        <p className="field__hint">Anime with an unknown start year are left out.</p>
      </fieldset>

      <Field
        name="min_score"
        label="Minimum score (0–10)"
        errors={errors.min_score}
        hint="Unscored anime are left out."
      >
        <DebouncedInput
          id={fieldIds("min_score").control}
          type="number"
          inputMode="decimal"
          min={0}
          max={10}
          step={0.1}
          value={query.min_score === undefined ? "" : String(query.min_score)}
          onCommit={(text) => onChange("min_score", toNumber(text))}
          {...errorAria("min_score", errors.min_score)}
        />
      </Field>

      <Field name="on_watchlist" label="Your watchlist" errors={errors.on_watchlist}>
        <Select
          id={fieldIds("on_watchlist").control}
          value={query.on_watchlist === undefined ? "" : String(query.on_watchlist)}
          onChange={(e) => onChange("on_watchlist", e.target.value === "" ? undefined : e.target.value === "true")}
          {...errorAria("on_watchlist", errors.on_watchlist)}
        >
          <option value="">On it or not</option>
          <option value="true">Only on your watchlist</option>
          <option value="false">Only not on it</option>
        </Select>
      </Field>

      <Field name="watchlist_status" label="Watch status" errors={errors.watchlist_status}>
        <Select
          id={fieldIds("watchlist_status").control}
          value={query.watchlist_status ?? ""}
          onChange={(e) =>
            onChange(
              "watchlist_status",
              e.target.value === "" ? undefined : (e.target.value as AnimeListQuery["watchlist_status"]),
            )
          }
          {...errorAria("watchlist_status", errors.watchlist_status)}
        >
          <option value="">Any watch status</option>
          {WATCH_STATUSES.map((s) => (
            <option key={s} value={s}>
              {watchStatusLabel(s)}
            </option>
          ))}
        </Select>
      </Field>
    </form>
  );
}
