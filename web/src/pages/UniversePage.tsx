import { useMemo, useState } from "react";
import { useAllAnime, useFranchises } from "../api/hooks";
import { Empty, Loading, ProblemView } from "../components/states";
import { useMediaQuery } from "../lib/useMedia";
import { ChipGroup, ChipRow } from "../universe/FilterChips";
import { Legend } from "../universe/Legend";
import {
  NO_FILTERS,
  formatOptions,
  hasFilters,
  matchesFilters,
  mergeFranchises,
  statusOptions,
  type UniverseFilters,
} from "../universe/model";
import { SideColumn } from "../universe/SideColumn";
import { UniverseList } from "../universe/UniverseList";
import { UniverseMap } from "../universe/UniverseMap";

type View = "map" | "list";

export function UniversePage() {
  const franchises = useFranchises();
  const anime = useAllAnime();
  const [filters, setFilters] = useState<UniverseFilters>(NO_FILTERS);
  const [view, setView] = useState<View>("map");
  const narrow = useMediaQuery("(max-width: 720px)");

  const all = anime.data;
  const merged = useMemo(
    () => (franchises.data && all ? mergeFranchises(franchises.data, all) : []),
    [franchises.data, all],
  );
  const statuses = useMemo(() => (all ? statusOptions(all) : []), [all]);
  const formats = useMemo(() => (all ? formatOptions(all) : []), [all]);
  const matching = useMemo(() => (all ? all.filter((a) => matchesFilters(a, filters)) : []), [all, filters]);

  let body;
  if (franchises.isPending || anime.isPending) {
    body = <Loading size="panel" label="Printing the universe…" />;
  } else if (franchises.isError || anime.isError) {
    body = (
      <ProblemView
        error={franchises.error ?? anime.error}
        onRetry={() => {
          void franchises.refetch();
          void anime.refetch();
        }}
      />
    );
  } else if (anime.data.length === 0) {
    body = (
      <Empty title="The universe is still dark">
        <p>
          No anime have been imported yet. Run <code>animeverse import</code> to fetch them from AniList, then reload
          this page.
        </p>
      </Empty>
    );
  } else {
    body = (
      <>
        <div className="toolbar">
          <ChipGroup
            label="Release status"
            options={statuses}
            value={filters.status}
            onChange={(status) => setFilters((f) => ({ ...f, status }))}
          />
          <ChipGroup
            label="Format"
            options={formats}
            value={filters.format}
            onChange={(format) => setFilters((f) => ({ ...f, format }))}
          />
          <ChipRow label="View" className="chips--view">
            <button type="button" className="chip" aria-pressed={view === "map"} onClick={() => setView("map")}>
              Map
            </button>
            <button type="button" className="chip" aria-pressed={view === "list"} onClick={() => setView("list")}>
              List
            </button>
          </ChipRow>
        </div>
        {hasFilters(filters) ? (
          <p className="filter-note" aria-live="polite">
            {/* The list's caption already gives the count; the map needs it said here. */}
            {view === "map" ? `${matching.length} of ${anime.data.length} anime match. The others are drawn as outlines. ` : null}
            <button type="button" className="link-button" onClick={() => setFilters(NO_FILTERS)}>
              Clear filters
            </button>
          </p>
        ) : null}
        {view === "map" ? (
          <UniverseMap anime={anime.data} franchises={merged} filters={filters} shape={narrow ? "tall" : "wide"} />
        ) : (
          <UniverseList anime={matching} total={anime.data.length} />
        )}
      </>
    );
  }

  const loaded = Boolean(all && franchises.data && all.length > 0);
  const dek = loaded ? (
    <p className={`spread__dek${narrow ? "" : " spread__dek--below"}`}>
      {all!.length} anime in {merged.length} franchises.{" "}
      {narrow
        ? "Pick a franchise to dive in, then tap a star to open it."
        : "Hover or focus a star for its card; pick a name plate to dive in."}
    </p>
  ) : null;

  // On wide screens the stage (title, toolbar and map) is sized to the viewport, so the
  // whole universe is visible at once; the legend and intro follow below it.
  return (
    <div className="spread">
      <section className="spread__main" aria-labelledby="universe-title">
        <div className="stage">
          <div className="spread__head">
            <h1 id="universe-title" className="spread__title">
              The Universe
            </h1>
            {narrow ? dek : null}
          </div>
          {body}
        </div>
        {loaded && view === "map" ? <Legend /> : null}
        {narrow ? null : dek}
      </section>
      <SideColumn />
    </div>
  );
}
