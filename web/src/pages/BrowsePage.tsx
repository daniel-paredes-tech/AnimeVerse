import { useMemo, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ApiError } from "../api/errors";
import { useAnimePage, useFranchises } from "../api/hooks";
import type { AnimeListQuery, Franchise } from "../api/types";
import { FieldErrors, Select, errorAria, fieldIds } from "../browse/fields";
import { FilterRail, type FieldErrorMap } from "../browse/FilterRail";
import {
  DEFAULT_PAGE_SIZE,
  DEFAULT_SORT,
  FILTER_PARAMS,
  SORTS,
  activeFilters,
  browseHref,
  browseHrefFromApiLink,
  parseBrowseQuery,
  withParam,
  withoutFilters,
  type FilterParam,
  type Param,
} from "../browse/query";
import { BROWSE_TONE_PREFIX, ResultCard } from "../browse/ResultCard";
import { Empty, Loading, ProblemView } from "../components/states";
import { formatLabel, releaseStatusLabel, watchStatusLabel } from "../lib/labels";
import { stockByFranchiseId } from "../universe/palette";
import { ToneDefs } from "../universe/StarGlyph";

const PAGE_SIZES = [24, 48, 100];
/** Fields that have their own control on this page (their API errors are shown there). */
const CONTROLLED: ReadonlySet<string> = new Set<string>([...FILTER_PARAMS, "sort", "page_size"]);

/** A short description of one active filter, for the tags above the results. */
export function filterTag(key: FilterParam, query: AnimeListQuery, franchises: readonly Franchise[] | undefined): string {
  switch (key) {
    case "q":
      return `Title contains “${query.q}”`;
    case "franchise":
      return franchises?.find((f) => f.id === query.franchise)?.name ?? `Franchise ${query.franchise}`;
    case "status":
      return releaseStatusLabel(query.status ?? null);
    case "format":
      return formatLabel(query.format ?? null);
    case "year_from":
      return `Started ${query.year_from} or later`;
    case "year_to":
      return `Started ${query.year_to} or earlier`;
    case "min_score":
      return `Score ${query.min_score} or more`;
    case "on_watchlist":
      return query.on_watchlist ? "On your watchlist" : "Not on your watchlist";
    case "watchlist_status":
      return `Watch status: ${query.watchlist_status ? watchStatusLabel(query.watchlist_status) : ""}`;
  }
}

function RemoveMark() {
  return (
    <svg className="tag__x" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">
      <path d="M1.5 1.5 8.5 8.5M8.5 1.5 1.5 8.5" />
    </svg>
  );
}

export function BrowsePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = useMemo(() => parseBrowseQuery(searchParams), [searchParams]);
  const franchises = useFranchises();
  const page = useAnimePage(query, { keepPrevious: true });
  const resultsTitle = useRef<HTMLHeadingElement>(null);

  const stocks = useMemo(() => stockByFranchiseId((franchises.data ?? []).map((f) => f.id)), [franchises.data]);
  const active = activeFilters(query);

  const go = (next: AnimeListQuery) => navigate(browseHref(next));
  const change = <K extends Param>(key: K, value: AnimeListQuery[K] | undefined) => go(withParam(query, key, value));
  const clearAll = () => go(withoutFilters(query));
  /** After moving to another page, put keyboard focus (and the view) on the results. */
  const focusResults = () => window.requestAnimationFrame(() => resultsTitle.current?.focus());

  const apiError = page.error instanceof ApiError ? page.error : null;
  const invalid = apiError !== null && (apiError.status === 400 || apiError.status === 422);
  const fieldErrors: FieldErrorMap = invalid ? apiError.fieldErrorMap() : {};
  const otherErrors = invalid ? apiError.fieldErrors.filter((e) => !CONTROLLED.has(e.field)) : [];

  const data = page.isError ? undefined : page.data;
  const meta = data?.meta;
  const countText = meta
    ? meta.total_items === 0
      ? "No anime match"
      : `${meta.total_items} ${meta.total_items === 1 ? "anime matches" : "anime match"} · page ${meta.page} of ${meta.total_pages}`
    : page.isError
      ? "No results"
      : "Loading…";

  const sortValue = query.sort ?? DEFAULT_SORT;
  const pageSize = query.page_size ?? DEFAULT_PAGE_SIZE;
  const sizes = PAGE_SIZES.includes(pageSize) ? PAGE_SIZES : [...PAGE_SIZES, pageSize].sort((a, b) => a - b);

  let results;
  if (page.isPending) {
    results = <Loading size="panel" label="Setting the index pages…" />;
  } else if (page.isError && invalid) {
    results = (
      <div className="refused" role="alert">
        <div className="problem__balloon">
          <p className="problem__title">{apiError.problem?.title ?? "Invalid request"}</p>
          <p className="problem__detail">{apiError.problem?.detail}</p>
          {otherErrors.length > 0 ? (
            <ul className="refused__list">
              {otherErrors.map((e, i) => (
                <li key={i}>
                  <code>{e.field || "request"}</code>: {e.message}
                </li>
              ))}
            </ul>
          ) : (
            <p>The API's message is shown next to the filter it is about.</p>
          )}
          <p className="refused__actions">
            <button type="button" className="button button--ink" onClick={clearAll}>
              Clear all filters
            </button>
            <Link className="button" to="/anime">
              Start over
            </Link>
          </p>
        </div>
      </div>
    );
  } else if (page.isError) {
    results = <ProblemView error={page.error} onRetry={() => void page.refetch()} />;
  } else if (data && data.data.length === 0 && data.meta.total_items > 0) {
    results = (
      <Empty
        title={`Page ${data.meta.page} is past the end`}
        action={
          <Link className="button button--ink" to={browseHref(withParam(query, "page", undefined))} onClick={focusResults}>
            Go to page 1
          </Link>
        }
      >
        <p>
          These filters match {data.meta.total_items} anime on {data.meta.total_pages}{" "}
          {data.meta.total_pages === 1 ? "page" : "pages"}.
        </p>
      </Empty>
    );
  } else if (data && data.data.length === 0) {
    results = (
      <Empty
        title="No anime match these filters"
        action={
          active.length > 0 ? (
            <button type="button" className="button button--ink" onClick={clearAll}>
              Clear all filters
            </button>
          ) : (
            <Link to="/">Back to the universe</Link>
          )
        }
      >
        {active.length > 0 ? (
          <p>
            Remove one of the {active.length === 1 ? "filter" : `${active.length} filters`} above to loosen the search,
            or clear them all.
          </p>
        ) : (
          <p>
            The catalogue is empty. Run <code>animeverse import</code> to fetch anime from AniList.
          </p>
        )}
      </Empty>
    );
  } else if (data) {
    results = (
      <>
        <ol className="results__grid" aria-labelledby="results-title">
          {data.data.map((anime) => (
            <ResultCard key={anime.id} anime={anime} stocks={stocks} />
          ))}
        </ol>
        <nav className="pager" aria-label="Pages">
          {data.links.prev ? (
            <Link className="button" to={browseHrefFromApiLink(data.links.prev)} onClick={focusResults} rel="prev">
              Previous page
            </Link>
          ) : (
            <span className="button button--disabled" aria-disabled="true">
              Previous page
            </span>
          )}
          <span className="pager__where">
            Page {data.meta.page} of {data.meta.total_pages}
          </span>
          {data.links.next ? (
            <Link className="button button--ink" to={browseHrefFromApiLink(data.links.next)} onClick={focusResults} rel="next">
              Next page
            </Link>
          ) : (
            <span className="button button--disabled" aria-disabled="true">
              Next page
            </span>
          )}
        </nav>
      </>
    );
  }

  return (
    <div className="browse">
      <svg width="0" height="0" className="browse__defs" aria-hidden="true">
        <defs>
          <ToneDefs idPrefix={BROWSE_TONE_PREFIX} />
        </defs>
      </svg>
      <h1 className="browse__title">Browse</h1>
      <div className="browse__layout">
        <FilterRail
          query={query}
          franchises={franchises.data}
          errors={fieldErrors}
          onChange={change}
          onClearAll={clearAll}
        />
        <section className="results" aria-labelledby="results-title" aria-busy={page.isFetching}>
          <div className="results__head">
            <div className="results__summary">
              <h2 id="results-title" className="results__title" ref={resultsTitle} tabIndex={-1}>
                Results
              </h2>
              <p className="results__count" aria-live="polite">
                {countText}
              </p>
            </div>
            <div className="results__controls">
              <div className="inline-field">
                <label className="field__label" htmlFor={fieldIds("sort").control}>
                  Order
                </label>
                <Select
                  id={fieldIds("sort").control}
                  value={sortValue}
                  onChange={(e) => change("sort", e.target.value as AnimeListQuery["sort"])}
                  {...errorAria("sort", fieldErrors.sort)}
                >
                  {SORTS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </Select>
                <FieldErrors name="sort" errors={fieldErrors.sort} />
              </div>
              <div className="inline-field">
                <label className="field__label" htmlFor={fieldIds("page_size").control}>
                  Per page
                </label>
                <Select
                  id={fieldIds("page_size").control}
                  value={pageSize}
                  onChange={(e) => change("page_size", Number(e.target.value))}
                  {...errorAria("page_size", fieldErrors.page_size)}
                >
                  {sizes.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
                <FieldErrors name="page_size" errors={fieldErrors.page_size} />
              </div>
            </div>
          </div>
          {active.length > 0 ? (
            <ul className="tags" aria-label="Active filters">
              {active.map((key) => (
                <li key={key}>
                  <button
                    type="button"
                    className="tag"
                    aria-label={`Remove filter: ${filterTag(key, query, franchises.data)}`}
                    onClick={() => change(key, undefined)}
                  >
                    {filterTag(key, query, franchises.data)}
                    <RemoveMark />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <div className={`results__body${page.isFetching && !page.isPending ? " results__body--updating" : ""}`}>
            {page.isFetching && !page.isPending ? <div className="results__roller" aria-hidden="true" /> : null}
            {results}
          </div>
        </section>
      </div>
    </div>
  );
}
