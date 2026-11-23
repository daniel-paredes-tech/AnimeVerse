import { Link } from "react-router";
import { useAnimePage } from "../api/hooks";
import { Empty, Loading, ProblemView } from "../components/states";
import { formatLabel, scoreLabel, startYearLabel } from "../lib/labels";

/** Browse: a plain first page for now; filters, sort and paging come next. */
export function BrowsePage() {
  const page = useAnimePage({ sort: "-popularity", page_size: 24 });
  return (
    <div className="page">
      <h1 className="page__title">Browse</h1>
      {page.isPending ? (
        <Loading label="Setting the catalogue pages…" />
      ) : page.isError ? (
        <ProblemView error={page.error} onRetry={() => void page.refetch()} />
      ) : page.data.data.length === 0 ? (
        <Empty title="No anime yet" action={<Link to="/">Back to the universe</Link>}>
          <p>
            Run <code>animeverse import</code> to fetch anime from AniList.
          </p>
        </Empty>
      ) : (
        <>
          <p className="narration">
            The {page.data.data.length} most popular of {page.data.meta.total_items} anime. Filters and sorting are
            being drawn for the next issue.
          </p>
          <ol className="plain-list">
            {page.data.data.map((anime) => (
              <li key={anime.id}>
                <Link to={`/anime/${anime.id}`}>{anime.title}</Link>{" "}
                <span>
                  {formatLabel(anime.format)} · {startYearLabel(anime.start_year)} · {scoreLabel(anime.score)}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
