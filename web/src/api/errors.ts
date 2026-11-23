import type { FieldError, Problem, ValidationProblem } from "./types";

/**
 * Every failed API call becomes an ApiError.
 *
 * - `problem` is the RFC 9457 body the API sent (every non-2xx is one, per the
 *   contract). It is `null` only when no problem arrived at all: the API was not
 *   reachable, or something between us and it answered instead.
 * - `fieldErrors` is the problem's `errors` list (400 and 422), so a form can put each
 *   message next to its input with `messagesFor("episodes_watched")`.
 */
export class ApiError extends Error {
  override readonly name = "ApiError";
  readonly status: number | null;
  readonly problem: Problem | ValidationProblem | null;
  readonly fieldErrors: readonly FieldError[];

  constructor(status: number | null, problem: Problem | ValidationProblem | null, message?: string) {
    super(message ?? problem?.detail ?? "The request failed.");
    this.status = status;
    this.problem = problem;
    this.fieldErrors = problem && "errors" in problem && Array.isArray(problem.errors) ? problem.errors : [];
  }

  /** The API could not be reached (it is not running, or the network failed). */
  get isNetworkError(): boolean {
    return this.status === null;
  }

  /** The database is stopped (`503 service-unavailable`). */
  get isServiceUnavailable(): boolean {
    return this.status === 503;
  }

  /** The messages for one field (`field` as the API names it, e.g. `episodes_watched`). */
  messagesFor(field: string): string[] {
    return this.fieldErrors.filter((error) => error.field === field).map((error) => error.message);
  }

  /** Field errors grouped by field name. The empty name is the body as a whole. */
  fieldErrorMap(): Record<string, string[]> {
    const map: Record<string, string[]> = {};
    for (const error of this.fieldErrors) {
      (map[error.field] ??= []).push(error.message);
    }
    return map;
  }
}

function isFieldError(value: unknown): value is FieldError {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.location === "string" &&
    typeof v.field === "string" &&
    typeof v.code === "string" &&
    typeof v.message === "string"
  );
}

/** True when `value` has the contract's `Problem` shape (the body is untrusted input). */
export function isProblem(value: unknown): value is Problem | ValidationProblem {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  const base =
    typeof v.type === "string" &&
    typeof v.title === "string" &&
    typeof v.status === "number" &&
    typeof v.detail === "string" &&
    typeof v.instance === "string";
  if (!base) return false;
  if ("errors" in v) return Array.isArray(v.errors) && v.errors.every(isFieldError);
  return true;
}

/** Builds the ApiError for a non-2xx response whose body has already been read. */
export function errorFromResponse(response: Response, body: unknown): ApiError {
  if (isProblem(body)) return new ApiError(response.status, body);
  return new ApiError(
    response.status,
    null,
    `The API answered ${response.status} without a problem description.`,
  );
}

export function networkError(cause: unknown): ApiError {
  const error = new ApiError(null, null, "The API could not be reached.");
  (error as { cause?: unknown }).cause = cause;
  return error;
}
