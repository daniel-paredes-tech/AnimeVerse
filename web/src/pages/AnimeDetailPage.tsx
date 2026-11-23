import { Link, useParams } from "react-router";
import { useAnime } from "../api/hooks";
import { Loading, ProblemView } from "../components/states";
import {
  englishTitleLabel,
  episodesLabel,
  formatLabel,
  franchiseNames,
  releaseStatusLabel,
  scoreLabel,
  startYearLabel,
} from "../lib/labels";
import { NotFoundPage } from "./NotFoundPage";

const MAX_ID = 2_147_483_647;

/** Parses the `:id` route segment the way the contract's `anime_id` allows it. */
export function parseAnimeId(raw: string | undefined): number | null {
  if (!raw || !/^[1-9][0-9]*$/.test(raw)) return null;
  const id = Number(raw);
  return id <= MAX_ID ? id : null;
}

export function AnimeDetailPage() {
  const id = parseAnimeId(useParams().id);
  if (id === null) return <NotFoundPage />;
  return <AnimeDetail id={id} />;
}

/** The detail page, short for now: the full page and the watchlist postcard come next. */
function AnimeDetail({ id }: { id: number }) {
  const query = useAnime(id);
  if (query.isPending) return <Loading size="panel" label="Pulling this anime's page…" />;
  if (query.isError) {
    return (
      <div className="page page--narrow">
        <ProblemView error={query.error} onRetry={() => void query.refetch()} />
        <p>
          <Link to="/">Back to the universe</Link>
        </p>
      </div>
    );
  }
  const anime = query.data;
  return (
    <div className="page page--narrow">
      <h1 className="page__title">{anime.title}</h1>
      <dl className="facts">
        <dt>English title</dt>
        <dd>{englishTitleLabel(anime)}</dd>
        <dt>Native title</dt>
        <dd lang={anime.title_japanese ? "ja" : undefined}>{anime.title_japanese ?? "No native title"}</dd>
        <dt>Franchise</dt>
        <dd>{franchiseNames(anime)}</dd>
        <dt>Format</dt>
        <dd>{formatLabel(anime.format)}</dd>
        <dt>Release status</dt>
        <dd>{releaseStatusLabel(anime.status)}</dd>
        <dt>Episodes</dt>
        <dd>{episodesLabel(anime.episodes)}</dd>
        <dt>Start year</dt>
        <dd>{startYearLabel(anime.start_year)}</dd>
        <dt>Score</dt>
        <dd>{scoreLabel(anime.score)}</dd>
      </dl>
      <p>
        {anime.anilist_url ? (
          <a href={anime.anilist_url} rel="noreferrer">
            Open on AniList
          </a>
        ) : (
          "AniList page unknown"
        )}
        {" · "}
        <Link to="/">Back to the universe</Link>
      </p>
    </div>
  );
}
