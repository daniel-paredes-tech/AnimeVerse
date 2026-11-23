import type { ReactNode } from "react";
import { ApiError } from "../api/errors";

/** Loading, in print: a press roller of screentone sweeping over the panel. */
export function Loading({ label, size = "box" }: { label: string; size?: "panel" | "box" }) {
  return (
    <div className={`loading loading--${size}`} role="status" aria-live="polite">
      <div className="loading__tone" aria-hidden="true" />
      <p className="narration loading__label">{label}</p>
    </div>
  );
}

/** Nothing to show, and what to do about it. */
export function Empty({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty narration">
      <p className="empty__title">{title}</p>
      <div className="empty__text">{children}</div>
      {action ? <div className="empty__action">{action}</div> : null}
    </div>
  );
}

interface ProblemViewProps {
  error: unknown;
  onRetry?: () => void;
  /** Compact for a side box; the default fills a panel. */
  compact?: boolean;
}

/**
 * Shows an API problem as the API sent it: its `title` and `detail`, plus the status and
 * the request path, and a way to try again. A 503 means the database is stopped, so it
 * also says how to start it.
 */
export function ProblemView({ error, onRetry, compact = false }: ProblemViewProps) {
  const apiError = error instanceof ApiError ? error : null;
  const problem = apiError?.problem ?? null;

  let title: string;
  let detail: string;
  if (problem) {
    title = problem.title;
    detail = problem.detail;
  } else if (apiError?.isNetworkError) {
    title = "The API isn't answering";
    detail = "AnimeVerse couldn't reach its API on this computer. Start it with `animeverse serve`, then try again.";
  } else if (apiError) {
    title = "Unexpected answer from the API";
    detail = apiError.message;
  } else {
    title = "Something went wrong";
    detail = error instanceof Error ? error.message : "An unknown error happened.";
  }

  const status = apiError?.status ?? null;
  return (
    <div className={`problem${compact ? " problem--compact" : ""}`} role="alert">
      <div className="problem__balloon">
        <p className="problem__title">{title}</p>
        <p className="problem__detail">{renderCode(detail)}</p>
        {status === 503 ? (
          <p className="problem__hint">
            The database is stopped. Start it from the project folder with <code>docker compose up -d</code>, wait
            until it is healthy, then retry.
          </p>
        ) : null}
        {problem ? (
          <p className="problem__meta">
            HTTP {problem.status} · <code>{problem.instance}</code>
          </p>
        ) : null}
        {onRetry ? (
          <button type="button" className="button button--ink" onClick={onRetry}>
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** Renders `backticked` parts of a message as code. */
function renderCode(text: string): ReactNode {
  const parts = text.split(/`([^`]+)`/);
  return parts.map((part, i) => (i % 2 === 1 ? <code key={i}>{part}</code> : part));
}
