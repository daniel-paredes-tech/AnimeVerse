import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { errorFromResponse, networkError } from "./errors";
import type { AnimeListQuery, AnimePage } from "./types";

/**
 * The paths in the contract already start with `/v1`, and its server URL is `/`, so the
 * base URL is this page's own origin: in development Vite proxies `/v1` to the API, in
 * production the API serves this app itself.
 */
function baseUrl(): string {
  return globalThis.location?.origin ?? "";
}

// `fetch` is looked up on every call (not captured once), so tests can stub it.
export const api = createClient<paths>({
  baseUrl: baseUrl(),
  fetch: (request) => globalThis.fetch(request),
  headers: { Accept: "application/json" },
});

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Awaits an openapi-fetch call and returns its data, or throws an ApiError. */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await call;
  } catch (cause) {
    throw networkError(cause);
  }
  if (!result.response.ok || result.data === undefined) {
    throw errorFromResponse(result.response, result.error);
  }
  return result.data;
}

/** Fetches one page of `GET /v1/anime`. */
export function fetchAnimePage(query: AnimeListQuery, signal?: AbortSignal): Promise<AnimePage> {
  return unwrap(api.GET("/v1/anime", { params: { query }, signal }));
}

/**
 * Follows a `links.next` (or `prev`) URL from an AnimePage. The link is ready-made by the
 * API (same filters, sort and page size), so it is requested as is.
 */
export async function fetchAnimePageByLink(link: string, signal?: AbortSignal): Promise<AnimePage> {
  const url = new URL(link, baseUrl() || undefined);
  if (url.origin !== baseUrl() && baseUrl() !== "") {
    throw new Error(`Refusing to follow a link to another origin: ${url.origin}`);
  }
  let response: Response;
  try {
    response = await globalThis.fetch(url, { headers: { Accept: "application/json" }, signal });
  } catch (cause) {
    throw networkError(cause);
  }
  let body: unknown = undefined;
  try {
    body = await response.json();
  } catch {
    // An empty or non-JSON body is reported below.
  }
  if (!response.ok) throw errorFromResponse(response, body);
  return body as AnimePage;
}

/**
 * Every anime, for the universe map: pages of 100 (the contract's maximum), following
 * `links.next` until it is `null`. The number of pages is never assumed.
 */
export async function fetchAllAnime(
  query: Omit<AnimeListQuery, "page" | "page_size"> = {},
  signal?: AbortSignal,
): Promise<AnimePage["data"]> {
  let page = await fetchAnimePage({ ...query, page_size: 100 }, signal);
  const all = [...page.data];
  const seen = new Set<string>([page.links.self]);
  while (page.links.next !== null) {
    if (seen.has(page.links.next)) {
      throw new Error(`The API sent the same next link twice: ${page.links.next}`);
    }
    seen.add(page.links.next);
    page = await fetchAnimePageByLink(page.links.next, signal);
    all.push(...page.data);
  }
  return all;
}
