import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { useAllAnime, useAnimePage } from "./hooks";
import type { AnimePage, AnimeSummary, Problem } from "./types";

// Shaped exactly like the contract's examples (components/examples/AnimePage).
const naruto: AnimeSummary = {
  id: 1,
  anilist_id: 20,
  title: "NARUTO",
  title_english: "Naruto",
  title_japanese: "NARUTO -ナルト-",
  format: "TV",
  status: "FINISHED",
  episodes: 220,
  start_year: 2002,
  end_year: 2007,
  score: 8.0,
  popularity: 743139,
  image_url: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/bx20-dE6UHbFFg1A5.jpg",
  franchises: [{ id: 1, name: "Naruto" }],
  watchlist_entry: null,
};

const shippuden: AnimeSummary = {
  id: 5,
  anilist_id: 1735,
  title: "NARUTO: Shippuuden",
  title_english: "Naruto: Shippuden",
  title_japanese: "NARUTO -ナルト- 疾風伝",
  format: "TV",
  status: "FINISHED",
  episodes: 500,
  start_year: 2007,
  end_year: 2017,
  score: 8.2,
  popularity: 624795,
  image_url: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/bx1735-kGfVm0YqCPcu.png",
  franchises: [{ id: 1, name: "Naruto" }],
  watchlist_entry: {
    anime_id: 5,
    status: "watching",
    episodes_watched: 110,
    rating: 9,
    notes: "Rewatch the Chunin exam arc.",
    created_at: "2026-11-23T18:00:00Z",
    updated_at: "2026-11-23T18:00:00Z",
  },
};

const unscored: AnimeSummary = {
  ...naruto,
  id: 9,
  anilist_id: 999,
  title: "Some Special",
  title_english: null,
  title_japanese: null,
  format: null,
  score: null,
  episodes: null,
  start_year: null,
  popularity: null,
  image_url: null,
};

function page(data: AnimeSummary[], n: number, totalPages: number, totalItems: number): AnimePage {
  const link = (p: number) => `/v1/anime?sort=-popularity&page=${p}&page_size=100`;
  return {
    data,
    meta: { page: n, page_size: 100, total_items: totalItems, total_pages: totalPages },
    links: { self: link(n), next: n < totalPages ? link(n + 1) : null, prev: n > 1 ? link(n - 1) : null },
  };
}

function json(body: unknown, status = 200, type = "application/json"): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": type } });
}

function urlOf(input: RequestInfo | URL): URL {
  if (typeof input === "string") return new URL(input);
  if (input instanceof URL) return input;
  return new URL(input.url);
}

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useAllAnime", () => {
  it("follows links.next across pages until it is null", async () => {
    const pages = [page([naruto], 1, 3, 3), page([shippuden], 2, 3, 3), page([unscored], 3, 3, 3)];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      const n = Number(url.searchParams.get("page") ?? "1");
      return json(pages[n - 1]);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useAllAnime(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.map((a) => a.id)).toEqual([1, 5, 9]);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const first = urlOf(fetchMock.mock.calls[0]![0]);
    expect(first.pathname).toBe("/v1/anime");
    expect(first.searchParams.get("page_size")).toBe("100");
    // Pages 2 and 3 are the API's own links, requested as they came.
    const second = urlOf(fetchMock.mock.calls[1]![0]);
    expect(second.pathname + second.search).toBe(pages[0]!.links.next);
    const third = urlOf(fetchMock.mock.calls[2]![0]);
    expect(third.pathname + third.search).toBe(pages[1]!.links.next);
  });

  it("stops after one request when the first page has no next link", async () => {
    const fetchMock = vi.fn(async () => json(page([naruto, shippuden], 1, 1, 2)));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useAllAnime(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("turns a problem on a later page into an ApiError with the problem body", async () => {
    const down: Problem = {
      type: "urn:animeverse:problem:service-unavailable",
      title: "Service unavailable",
      status: 503,
      detail: "The database is unavailable. Try again later.",
      instance: "/v1/anime",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      urlOf(input).searchParams.get("page") === "2"
        ? json(down, 503, "application/problem+json")
        : json(page([naruto], 1, 2, 2)),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useAllAnime(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    const error = result.current.error;
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(503);
    expect((error as ApiError).problem).toEqual(down);
  });
});

describe("useAnimePage", () => {
  it("sends the filters and maps a 400's field errors by field", async () => {
    const invalid = {
      type: "urn:animeverse:problem:invalid-request",
      title: "Invalid request",
      status: 400,
      detail: "The request has 1 invalid parameter.",
      instance: "/v1/anime",
      errors: [{ location: "query", field: "page_size", code: "too_large", message: "Must be at most 100." }],
    };
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => json(invalid, 400, "application/problem+json"));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useAnimePage({ status: "RELEASING", sort: "-popularity", page_size: 5 }), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    const sent = urlOf(fetchMock.mock.calls[0]![0]);
    expect(sent.searchParams.get("status")).toBe("RELEASING");
    expect(sent.searchParams.get("page_size")).toBe("5");
    const error = result.current.error as ApiError;
    expect(error.messagesFor("page_size")).toEqual(["Must be at most 100."]);
    expect(error.fieldErrorMap()).toEqual({ page_size: ["Must be at most 100."] });
  });

  it("reports an unreachable API as a network error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    const { result } = renderHook(() => useAnimePage({}), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    const error = result.current.error as ApiError;
    expect(error.isNetworkError).toBe(true);
    expect(error.problem).toBeNull();
  });
});
