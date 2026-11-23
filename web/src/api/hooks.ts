import { QueryClient, useQuery } from "@tanstack/react-query";
import { api, fetchAllAnime, fetchAnimePage, unwrap } from "./client";
import { ApiError } from "./errors";
import type { AnimeListQuery } from "./types";

export const queryKeys = {
  franchises: ["franchises"] as const,
  animePage: (query: AnimeListQuery) => ["anime", "page", query] as const,
  allAnime: ["anime", "all"] as const,
  anime: (id: number) => ["anime", "one", id] as const,
};

/** Retry once when the API was unreachable or failed (5xx), never for 4xx answers. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError) {
    if (error.status === 503) return false; // the database is stopped: say so at once
    if (error.status !== null && error.status < 500) return false;
  }
  return failureCount < 1;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 60_000,
        refetchOnWindowFocus: false,
      },
    },
  });
}

/** `GET /v1/franchises`: every franchise with its anime count. */
export function useFranchises() {
  return useQuery({
    queryKey: queryKeys.franchises,
    queryFn: ({ signal }) => unwrap(api.GET("/v1/franchises", { signal })),
    select: (list) => list.data,
  });
}

/** One page of `GET /v1/anime`, with any filters, sort and page. */
export function useAnimePage(query: AnimeListQuery) {
  return useQuery({
    queryKey: queryKeys.animePage(query),
    queryFn: ({ signal }) => fetchAnimePage(query, signal),
  });
}

/** Every anime, for the universe map (follows `links.next` to the end). */
export function useAllAnime() {
  return useQuery({
    queryKey: queryKeys.allAnime,
    queryFn: ({ signal }) => fetchAllAnime({ sort: "-popularity" }, signal),
  });
}

/** `GET /v1/anime/{anime_id}`. */
export function useAnime(id: number) {
  return useQuery({
    queryKey: queryKeys.anime(id),
    queryFn: ({ signal }) =>
      unwrap(api.GET("/v1/anime/{anime_id}", { params: { path: { anime_id: id } }, signal })),
  });
}
