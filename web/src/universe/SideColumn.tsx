import type { ReactNode } from "react";
import { Link } from "react-router";
import { useAnimePage } from "../api/hooks";
import type { AnimeListQuery, AnimeSummary } from "../api/types";
import { Empty, Loading, ProblemView } from "../components/states";
import { formatLabel, progressLabel, scoreLabel, startYearLabel } from "../lib/labels";

const BOX_SIZE = 5;

interface BoxProps {
  id: string;
  title: string;
  query: AnimeListQuery;
  browseHref: string;
  variant?: "next-issue";
  empty: { title: string; body: ReactNode; action?: ReactNode };
  meta: (anime: AnimeSummary) => ReactNode;
}

function SideBox({ id, title, query, browseHref, variant, empty, meta }: BoxProps) {
  const page = useAnimePage({ ...query, page_size: BOX_SIZE });
  const total = page.data?.meta.total_items;
  return (
    <section className={`side-box${variant ? ` side-box--${variant}` : ""}`} aria-labelledby={id}>
      <h2 className="side-box__title" id={id}>
        {title}{" "}
        {total !== undefined ? <span className="side-box__count">{total}</span> : null}
      </h2>
      {page.isPending ? (
        <Loading label="Setting type…" />
      ) : page.isError ? (
        <ProblemView compact error={page.error} onRetry={() => void page.refetch()} />
      ) : page.data.data.length === 0 ? (
        <Empty title={empty.title} action={empty.action}>
          {empty.body}
        </Empty>
      ) : (
        <>
          <ol className="side-box__list">
            {page.data.data.map((anime) => (
              <li key={anime.id} className="side-item">
                {anime.image_url ? (
                  <img className="side-item__cover" src={anime.image_url} alt="" width={40} height={57} loading="lazy" />
                ) : (
                  <span className="side-item__cover side-item__cover--none">No cover</span>
                )}
                <span className="side-item__text">
                  <Link className="side-item__title" to={`/anime/${anime.id}`}>
                    {anime.title}
                  </Link>
                  <span className="side-item__meta">{meta(anime)}</span>
                </span>
              </li>
            ))}
          </ol>
          {total !== undefined && total > page.data.data.length ? (
            <p className="side-box__more">
              <Link to={browseHref}>All {total}</Link>
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

function Progress({ anime }: { anime: AnimeSummary }) {
  const entry = anime.watchlist_entry;
  if (!entry) return null;
  const known = anime.episodes !== null && anime.episodes > 0;
  const share = known ? Math.min(1, entry.episodes_watched / anime.episodes!) : 0;
  return (
    <>
      {progressLabel(entry.episodes_watched, anime.episodes)}
      <span className={`meter${known ? "" : " meter--unknown"}`} aria-hidden="true">
        {known ? <span className="meter__fill" style={{ width: `${share * 100}%` }} /> : null}
      </span>
    </>
  );
}

/** The right-hand page: what is airing, what is coming, and what you are watching. */
export function SideColumn() {
  return (
    <aside className="side-column" aria-label="This week">
      <SideBox
        id="side-airing"
        title="Airing now"
        query={{ status: "RELEASING", sort: "-popularity" }}
        browseHref="/anime?status=RELEASING"
        meta={(a) => `${formatLabel(a.format)} · since ${startYearLabel(a.start_year)} · ${scoreLabel(a.score)}`}
        empty={{
          title: "Nothing is airing",
          body: <p>No anime in your catalogue is releasing right now.</p>,
          action: <Link to="/anime">Browse the catalogue</Link>,
        }}
      />
      <SideBox
        id="side-coming"
        title="Coming"
        query={{ status: "NOT_YET_RELEASED", sort: "start_year" }}
        browseHref="/anime?status=NOT_YET_RELEASED"
        meta={(a) => `${formatLabel(a.format)} · ${a.start_year === null ? "start year unknown" : `starts ${a.start_year}`}`}
        empty={{
          title: "Nothing announced",
          body: <p>No anime in your catalogue is waiting for release.</p>,
          action: <Link to="/anime">Browse the catalogue</Link>,
        }}
      />
      <SideBox
        id="side-watching"
        title="Continue watching"
        variant="next-issue"
        query={{ watchlist_status: "watching", sort: "-popularity" }}
        browseHref="/anime?watchlist_status=watching"
        meta={(a) => <Progress anime={a} />}
        empty={{
          title: "Your next issue is empty",
          body: (
            <p>
              Open any star, then log your progress on its page. Anime you are watching show up here with the episode
              you reached.
            </p>
          ),
        }}
      />
    </aside>
  );
}
