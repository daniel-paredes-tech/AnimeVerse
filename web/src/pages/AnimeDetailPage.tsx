import type { ReactNode } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "../api/errors";
import { useAnime, useFranchises } from "../api/hooks";
import type { AnimeDetail } from "../api/types";
import { Loading, ProblemView } from "../components/states";
import { WatchlistForm } from "../detail/WatchlistForm";
import {
  airDatesLabel,
  dateTimeLabel,
  endYearLabel,
  formatLabel,
  releaseStatusLabel,
  scoreLabel,
  startYearLabel,
} from "../lib/labels";
import { PAPER, stockByFranchiseId } from "../universe/palette";
import { scoreToneStep } from "../universe/screentone";
import { StarGlyph, ToneDefs } from "../universe/StarGlyph";
import { NotFoundPage } from "./NotFoundPage";

const MAX_ID = 2_147_483_647;
const TONE_PREFIX = "detail";

/** Parses the `:id` route segment the way the contract's `anime_id` allows it. */
export function parseAnimeId(raw: string | undefined): number | null {
  if (!raw || !/^[1-9][0-9]*$/.test(raw)) return null;
  const id = Number(raw);
  return id <= MAX_ID ? id : null;
}

export function AnimeDetailPage() {
  const id = parseAnimeId(useParams().id);
  if (id === null) return <NotFoundPage />;
  // Keyed by id: moving to another anime starts a fresh page and a fresh form.
  return <AnimeDetailView key={id} id={id} />;
}

function AnimeDetailView({ id }: { id: number }) {
  const query = useAnime(id);
  if (query.isPending) return <Loading size="panel" label="Pulling this anime's page…" />;
  if (query.isError) {
    const error = query.error;
    if (error instanceof ApiError && error.status === 404) {
      return <AnimeNotFound detail={error.problem?.detail ?? `There is no anime with id ${id}.`} />;
    }
    return (
      <div className="page page--narrow">
        <ProblemView error={error} onRetry={() => void query.refetch()} />
        <p>
          <Link to="/anime">Back to Browse</Link>
        </p>
      </div>
    );
  }
  return <AnimeSheet anime={query.data} />;
}

/** The API answered 404 for this id: say so in its words, with ways back. */
function AnimeNotFound({ detail }: { detail: string }) {
  return (
    <div className="page page--narrow not-found">
      <p className="not-found__code" aria-hidden="true">
        404
      </p>
      <h1 className="page__title">This anime isn't in the catalogue</h1>
      <p className="narration">{detail} It may have been removed by a later import, or the address was mistyped.</p>
      <p className="not-found__actions">
        <Link className="button button--red" to="/anime">
          Browse every anime
        </Link>
        <Link className="button" to="/">
          Back to the universe
        </Link>
      </p>
    </div>
  );
}

function Fact({ term, value, unknown = false }: { term: string; value: ReactNode; unknown?: boolean }) {
  return (
    <div className="sheet__fact">
      <dt>{term}</dt>
      <dd className={unknown ? "sheet__unknown" : undefined}>{value}</dd>
    </div>
  );
}

function AnimeSheet({ anime }: { anime: AnimeDetail }) {
  const franchises = useFranchises();
  const stocks = stockByFranchiseId((franchises.data ?? []).map((f) => f.id));
  const first = anime.franchises[0];
  const stock = first ? stocks.get(first.id) ?? PAPER : PAPER;

  return (
    <article className="sheet" aria-labelledby="anime-title">
      <svg width="0" height="0" className="browse__defs" aria-hidden="true">
        <defs>
          <ToneDefs idPrefix={TONE_PREFIX} />
        </defs>
      </svg>
      <p className="sheet__back">
        <Link to="/anime">Browse</Link>
        <span aria-hidden="true"> / </span>
        <span>{anime.title}</span>
      </p>

      <div className="sheet__layout">
        <div className="sheet__main">
          <header className="sheet__head">
            {anime.image_url ? (
              <img className="sheet__cover" src={anime.image_url} alt={`Cover of ${anime.title}`} width={150} height={214} />
            ) : (
              <span className="sheet__cover sheet__cover--none">No cover image</span>
            )}
            <div className="sheet__titles">
              <h1 className="sheet__title" id="anime-title">
                {anime.title}
              </h1>
              <p className={anime.title_english ? "sheet__english" : "sheet__english sheet__unknown"}>
                {anime.title_english ?? "No English title"}
              </p>
              {anime.title_japanese ? (
                <p className="sheet__native" lang="ja">
                  {anime.title_japanese}
                </p>
              ) : (
                <p className="sheet__native sheet__unknown">No native title</p>
              )}
              <div className="sheet__meta">
                <div className="sheet__score">
                  <svg viewBox="-20 -20 40 40" width="40" height="40" aria-hidden="true">
                    <StarGlyph r={17} stock={stock} toneStep={scoreToneStep(anime.score)} idPrefix={TONE_PREFIX} />
                  </svg>
                  <span className={anime.score === null ? "sheet__score-value sheet__unknown" : "sheet__score-value"}>
                    {anime.score === null ? "Unscored" : `Score ${scoreLabel(anime.score)}`}
                  </span>
                </div>
                <ul className="sheet__franchises" aria-label="Franchises">
                  {anime.franchises.length === 0 ? (
                    <li className="sheet__franchise" style={{ backgroundColor: PAPER }}>
                      No franchise
                    </li>
                  ) : (
                    anime.franchises.map((f) => (
                      <li key={f.id} className="sheet__franchise" style={{ backgroundColor: stocks.get(f.id) ?? PAPER }}>
                        <Link to={`/anime?franchise=${f.id}`}>{f.name}</Link>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            </div>
          </header>

          <dl className="sheet__facts">
            <Fact term="Format" value={formatLabel(anime.format)} unknown={anime.format === null} />
            <Fact term="Release status" value={releaseStatusLabel(anime.status)} unknown={anime.status === null} />
            <Fact
              term="Episodes"
              value={anime.episodes === null ? "Unknown" : anime.episodes}
              unknown={anime.episodes === null}
            />
            <Fact term="Started" value={startYearLabel(anime.start_year)} unknown={anime.start_year === null} />
            <Fact term="Ended" value={endYearLabel(anime.end_year)} unknown={anime.end_year === null} />
            <Fact
              term="Aired"
              value={airDatesLabel(anime.aired_from, anime.aired_to)}
              unknown={anime.aired_from === null || anime.aired_to === null}
            />
            <Fact
              term="Popularity"
              value={
                anime.popularity === null
                  ? "Unknown"
                  : `${anime.popularity.toLocaleString("en-GB")} AniList users have it on a list`
              }
              unknown={anime.popularity === null}
            />
            <Fact
              term="On AniList"
              value={
                anime.anilist_url ? (
                  <a href={anime.anilist_url} target="_blank" rel="noopener noreferrer">
                    Open its AniList page
                    <svg className="external" viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">
                      <path d="M5 2H2v8h8V7M7 2h3v3M10 2 5.5 6.5" />
                    </svg>
                    <span className="sr-only"> (opens in a new tab)</span>
                  </a>
                ) : (
                  "AniList page unknown"
                )
              }
              unknown={anime.anilist_url === null}
            />
            <Fact term="Last refreshed" value={dateTimeLabel(anime.updated_at)} />
          </dl>

          <section className="sheet__synopsis" aria-labelledby="synopsis-title">
            <h2 id="synopsis-title" className="sheet__h2">
              Synopsis
            </h2>
            {anime.synopsis ? (
              anime.synopsis
                .split(/\n{2,}|\n/)
                .filter((p) => p.trim() !== "")
                .map((p, i) => <p key={i}>{p}</p>)
            ) : (
              <p className="sheet__unknown">No synopsis.</p>
            )}
          </section>
        </div>

        <WatchlistForm anime={anime} />
      </div>
    </article>
  );
}
