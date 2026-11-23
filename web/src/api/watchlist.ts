import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { ApiError, errorFromResponse, networkError } from "./errors";
import type { components } from "./schema";
import type { WatchlistEntry } from "./types";

export type WatchlistEntryInput = components["schemas"]["WatchlistEntryInput"];

export interface SaveResult {
  entry: WatchlistEntry;
  /** `201`: the entry was created. `200`: an existing entry was replaced. */
  created: boolean;
}

/** `PUT /v1/anime/{anime_id}/watchlist-entry` with the contract's exact body. */
export async function putWatchlistEntry(animeId: number, body: WatchlistEntryInput): Promise<SaveResult> {
  let result;
  try {
    result = await api.PUT("/v1/anime/{anime_id}/watchlist-entry", {
      params: { path: { anime_id: animeId } },
      body,
    });
  } catch (cause) {
    throw networkError(cause);
  }
  const { data, error, response } = result;
  if (!response.ok || data === undefined) throw errorFromResponse(response, error);
  return { entry: data, created: response.status === 201 };
}

export interface RemoveResult {
  /** True when the API said there was no entry to remove (`404`): it is gone either way. */
  alreadyRemoved: boolean;
  /** The API's explanation in that case. */
  detail: string | null;
}

/**
 * `DELETE /v1/anime/{anime_id}/watchlist-entry`. A `404` because the entry no longer
 * exists counts as done; any other problem is thrown.
 */
export async function deleteWatchlistEntry(animeId: number): Promise<RemoveResult> {
  let result;
  try {
    result = await api.DELETE("/v1/anime/{anime_id}/watchlist-entry", {
      params: { path: { anime_id: animeId } },
    });
  } catch (cause) {
    throw networkError(cause);
  }
  const { error, response } = result;
  if (response.status === 204) return { alreadyRemoved: false, detail: null };
  const apiError = errorFromResponse(response, error);
  if (apiError.status === 404) return { alreadyRemoved: true, detail: apiError.problem?.detail ?? null };
  throw apiError;
}

/**
 * Every cached anime query (the map, Browse pages, the side column and the detail) shows
 * watchlist data, so all of them are refreshed after a write.
 */
function useRefreshAnime() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ["anime"] });
}

export function useSaveWatchlistEntry(animeId: number) {
  const refresh = useRefreshAnime();
  return useMutation<SaveResult, ApiError, WatchlistEntryInput>({
    mutationFn: (body) => putWatchlistEntry(animeId, body),
    onSuccess: () => refresh(),
  });
}

export function useRemoveWatchlistEntry(animeId: number) {
  const refresh = useRefreshAnime();
  return useMutation<RemoveResult, ApiError, void>({
    mutationFn: () => deleteWatchlistEntry(animeId),
    onSuccess: () => refresh(),
  });
}
