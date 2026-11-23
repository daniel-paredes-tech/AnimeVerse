import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import type { ApiError } from "../api/errors";
import type { AnimeDetail, WatchStatus, WatchlistEntry } from "../api/types";
import { useRemoveWatchlistEntry, useSaveWatchlistEntry, type WatchlistEntryInput } from "../api/watchlist";
import { ProblemView } from "../components/states";
import { dateTimeLabel, watchStatusLabel } from "../lib/labels";

const STATUSES: readonly WatchStatus[] = ["planning", "watching", "completed", "paused", "dropped"];
const RATINGS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;
const NOTES_MAX = 1000;
/** The body fields, in the order their controls appear (the first invalid one gets focus). */
const FIELDS = ["status", "episodes_watched", "rating", "notes"] as const;
type Field = (typeof FIELDS)[number];

interface Draft {
  status: WatchStatus;
  /** As typed: the API, not the form, decides whether it is valid. */
  episodes: string;
  rating: number | null;
  notes: string;
}

function draftFrom(entry: WatchlistEntry | null): Draft {
  return entry
    ? { status: entry.status, episodes: String(entry.episodes_watched), rating: entry.rating, notes: entry.notes ?? "" }
    : { status: "planning", episodes: "0", rating: null, notes: "" };
}

/**
 * The request body, exactly as the contract defines it: all four fields, `null` for no
 * rating and no notes. An episodes value that isn't a number is sent as `null`, so the
 * API's own validation answers it next to the field.
 */
export function toBody(draft: Draft): WatchlistEntryInput {
  const typed = draft.episodes.trim();
  const episodes = typed === "" ? Number.NaN : Number(typed);
  return {
    status: draft.status,
    episodes_watched: (Number.isFinite(episodes) ? episodes : null) as number,
    rating: draft.rating,
    notes: draft.notes === "" ? null : draft.notes,
  };
}

/** The hanko: printed only once the API has confirmed the save. */
function Stamp({ created, at }: { created: boolean; at: string }) {
  return (
    <div className="stamp" aria-hidden="true">
      <span className="stamp__word">{created ? "Added" : "Updated"}</span>
      <span className="stamp__date">{new Date(at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>
    </div>
  );
}

interface Notice {
  kind: "created" | "updated" | "removed";
  text: string;
  at: string;
}

export function WatchlistForm({ anime }: { anime: AnimeDetail }) {
  const ids = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const idOf = (name: string) => `${ids}-${name}`;
  const [entry, setEntry] = useState<WatchlistEntry | null>(anime.watchlist_entry);
  const [draft, setDraft] = useState<Draft>(() => draftFrom(anime.watchlist_entry));
  const [notice, setNotice] = useState<Notice | null>(null);
  const [confirming, setConfirming] = useState(false);
  const save = useSaveWatchlistEntry(anime.id);
  const remove = useRemoveWatchlistEntry(anime.id);
  const formRef = useRef<HTMLFormElement>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const noticeRef = useRef<HTMLParagraphElement>(null);

  const saveError: ApiError | null = save.error;
  const validation = saveError && (saveError.status === 422 || saveError.status === 400) ? saveError : null;
  const fieldErrors: Partial<Record<Field, string[]>> = {};
  const unmatched: { field: string; message: string }[] = [];
  for (const e of validation?.fieldErrors ?? []) {
    if ((FIELDS as readonly string[]).includes(e.field)) (fieldErrors[e.field as Field] ??= []).push(e.message);
    else unmatched.push({ field: e.field, message: e.message });
  }
  const invalid = (field: Field) => (fieldErrors[field]?.length ?? 0) > 0;
  const aria = (field: Field) =>
    invalid(field) ? { "aria-invalid": true as const, "aria-describedby": idOf(`${field}-errors`) } : {};

  // After the API refuses the entry, move focus to the first control it complained about.
  useEffect(() => {
    if (!validation) return;
    const first = FIELDS.find((f) => (fieldErrors[f]?.length ?? 0) > 0);
    const form = formRef.current;
    if (!form || !first) {
      summaryRef.current?.focus();
      return;
    }
    const target =
      first === "status" || first === "rating"
        ? (form.querySelector<HTMLInputElement>(`input[name="${idOf(first)}"]:checked`) ??
          form.querySelector<HTMLInputElement>(`input[name="${idOf(first)}"]`))
        : form.querySelector<HTMLElement>(`#${idOf(first)}`);
    target?.focus();
    // Run once per refused submission.
  }, [validation]);

  useEffect(() => {
    if (confirming) keepRef.current?.focus();
  }, [confirming]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setNotice(null);
    setConfirming(false);
    remove.reset();
    save.mutate(toBody(draft), {
      onSuccess: ({ entry: saved, created }) => {
        setEntry(saved);
        setNotice({
          kind: created ? "created" : "updated",
          text: created ? "Added to your watchlist." : "Your watchlist entry was updated.",
          at: saved.updated_at,
        });
      },
    });
  };

  const onRemove = () => {
    save.reset();
    remove.mutate(undefined, {
      onSuccess: ({ alreadyRemoved, detail }) => {
        setEntry(null);
        setDraft(draftFrom(null));
        setConfirming(false);
        setNotice({
          kind: "removed",
          text: alreadyRemoved
            ? `It was already off your watchlist${detail ? ` (${detail})` : ""}.`
            : "Removed from your watchlist.",
          at: new Date().toISOString(),
        });
        window.requestAnimationFrame(() => noticeRef.current?.focus());
      },
    });
  };

  const episodesNumber = Number(draft.episodes);
  const step = (delta: number) =>
    setDraft((d) => ({ ...d, episodes: String(Math.max(0, (Number.isFinite(episodesNumber) ? episodesNumber : 0) + delta)) }));
  const notesLeft = NOTES_MAX - draft.notes.length;

  return (
    <section className="postcard" aria-labelledby={idOf("title")}>
      <div className="postcard__head">
        <div>
          <h2 className="postcard__title" id={idOf("title")}>
            Your watchlist
          </h2>
          <p className="postcard__state">
            {entry
              ? `${watchStatusLabel(entry.status)} · on your watchlist since ${dateTimeLabel(entry.created_at)}, last changed ${dateTimeLabel(entry.updated_at)}.`
              : "Not on your watchlist."}
          </p>
        </div>
        <div className="postcard__stamp-box">
          {notice && notice.kind !== "removed" ? (
            <Stamp key={notice.at + notice.kind} created={notice.kind === "created"} at={notice.at} />
          ) : null}
        </div>
      </div>

      <p className="postcard__notice" role="status" ref={noticeRef} tabIndex={-1}>
        {notice?.text ?? ""}
      </p>

      {validation ? (
        <div className="postcard__summary" role="alert" ref={summaryRef} tabIndex={-1}>
          <p className="postcard__summary-title">{validation.problem?.title ?? "The entry was not saved"}</p>
          <p>{validation.problem?.detail}</p>
          {unmatched.length > 0 ? (
            <ul>
              {unmatched.map((e, i) => (
                <li key={i}>
                  {e.field ? <code>{e.field}</code> : "The entry"}: {e.message}
                </li>
              ))}
            </ul>
          ) : (
            <p>Each message is next to the field it is about.</p>
          )}
        </div>
      ) : saveError ? (
        <ProblemView compact error={saveError} onRetry={() => formRef.current?.requestSubmit()} />
      ) : null}

      <form ref={formRef} className="postcard__form" noValidate onSubmit={onSubmit}>
        <fieldset
          className={`survey${invalid("status") ? " survey--invalid" : ""}`}
          role="radiogroup"
          aria-labelledby={idOf("status-legend")}
          {...aria("status")}
        >
          <legend className="survey__legend" id={idOf("status-legend")}>
            Status
          </legend>
          <div className="survey__options">
            {STATUSES.map((s) => (
              <label key={s} className="tick">
                <input
                  type="radio"
                  name={idOf("status")}
                  value={s}
                  checked={draft.status === s}
                  onChange={() => setDraft((d) => ({ ...d, status: s }))}
                />
                <span className="tick__box" aria-hidden="true" />
                {watchStatusLabel(s)}
              </label>
            ))}
          </div>
          <Errors id={idOf("status-errors")} messages={fieldErrors.status} />
        </fieldset>

        <div className="survey">
          <label className="survey__legend" htmlFor={idOf("episodes_watched")}>
            Episodes watched
          </label>
          <div className="stepper">
            <button type="button" className="stepper__button" aria-label="One episode fewer" onClick={() => step(-1)}>
              <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
                <path d="M2 6h8" />
              </svg>
            </button>
            <input
              id={idOf("episodes_watched")}
              className="control stepper__input"
              type="number"
              inputMode="numeric"
              min={0}
              step={1}
              value={draft.episodes}
              onChange={(e) => setDraft((d) => ({ ...d, episodes: e.target.value }))}
              aria-describedby={[idOf("episodes-total"), invalid("episodes_watched") ? idOf("episodes_watched-errors") : ""]
                .filter(Boolean)
                .join(" ")}
              aria-invalid={invalid("episodes_watched") || undefined}
            />
            <button type="button" className="stepper__button" aria-label="One episode more" onClick={() => step(1)}>
              <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
                <path d="M2 6h8M6 2v8" />
              </svg>
            </button>
            <span className="stepper__total" id={idOf("episodes-total")}>
              {anime.episodes === null
                ? "episode count unknown"
                : `of ${anime.episodes} ${anime.episodes === 1 ? "episode" : "episodes"}`}
            </span>
          </div>
          <Errors id={idOf("episodes_watched-errors")} messages={fieldErrors.episodes_watched} />
        </div>

        <fieldset
          className={`survey${invalid("rating") ? " survey--invalid" : ""}`}
          role="radiogroup"
          aria-labelledby={idOf("rating-legend")}
          {...aria("rating")}
        >
          <legend className="survey__legend" id={idOf("rating-legend")}>
            Your rating
          </legend>
          <div className="survey__options survey__options--scale">
            <label className="tick tick--scale">
              <input
                type="radio"
                name={idOf("rating")}
                value=""
                checked={draft.rating === null}
                onChange={() => setDraft((d) => ({ ...d, rating: null }))}
              />
              <span className="tick__box" aria-hidden="true" />
              None
            </label>
            {RATINGS.map((r) => (
              <label key={r} className="tick tick--scale">
                <input
                  type="radio"
                  name={idOf("rating")}
                  value={r}
                  checked={draft.rating === r}
                  onChange={() => setDraft((d) => ({ ...d, rating: r }))}
                />
                <span className="tick__box" aria-hidden="true" />
                {r}
              </label>
            ))}
          </div>
          <Errors id={idOf("rating-errors")} messages={fieldErrors.rating} />
        </fieldset>

        <div className="survey">
          <label className="survey__legend" htmlFor={idOf("notes")}>
            Notes
          </label>
          <textarea
            id={idOf("notes")}
            className="control postcard__notes"
            rows={4}
            maxLength={NOTES_MAX}
            value={draft.notes}
            onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
            aria-describedby={[idOf("notes-count"), invalid("notes") ? idOf("notes-errors") : ""].filter(Boolean).join(" ")}
            aria-invalid={invalid("notes") || undefined}
          />
          <p className="postcard__count" id={idOf("notes-count")} aria-live={notesLeft <= 100 ? "polite" : "off"}>
            {draft.notes.length} / {NOTES_MAX} characters
          </p>
          <Errors id={idOf("notes-errors")} messages={fieldErrors.notes} />
        </div>

        <div className="postcard__actions">
          <button type="submit" className="button button--red" disabled={save.isPending}>
            {save.isPending ? "Saving…" : entry ? "Save changes" : "Add to watchlist"}
          </button>
          {entry && !confirming ? (
            <button type="button" className="button" onClick={() => setConfirming(true)}>
              Remove from watchlist
            </button>
          ) : null}
        </div>
      </form>

      {confirming ? (
        <div className="postcard__confirm" role="group" aria-labelledby={idOf("confirm")}>
          <p id={idOf("confirm")}>
            Remove <strong>{anime.title}</strong> from your watchlist? Your status, episodes, rating and notes for it
            are deleted.
          </p>
          <div className="postcard__actions">
            <button type="button" className="button button--ink" onClick={onRemove} disabled={remove.isPending}>
              {remove.isPending ? "Removing…" : "Yes, remove it"}
            </button>
            <button type="button" className="button" ref={keepRef} onClick={() => setConfirming(false)}>
              Keep it
            </button>
          </div>
        </div>
      ) : null}
      {remove.error ? <ProblemView compact error={remove.error} onRetry={onRemove} /> : null}
    </section>
  );
}

function Errors({ id, messages }: { id: string; messages: readonly string[] | undefined }) {
  if (!messages || messages.length === 0) return null;
  return (
    <div className="balloon" id={id}>
      {messages.map((m, i) => (
        <p key={i}>{m}</p>
      ))}
    </div>
  );
}
