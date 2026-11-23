import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div className="page page--narrow not-found">
      <p className="not-found__code" aria-hidden="true">
        404
      </p>
      <h1 className="page__title">This page isn't in this week's issue</h1>
      <p className="narration">
        The address doesn't match any page of AnimeVerse. It may have been mistyped, or the anime was removed in a
        later import.
      </p>
      <p className="not-found__actions">
        <Link className="button button--red" to="/">
          Back to the universe
        </Link>
        <Link className="button" to="/anime">
          Browse every anime
        </Link>
      </p>
    </div>
  );
}
