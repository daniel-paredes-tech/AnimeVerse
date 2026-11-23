import { describe, expect, it } from "vitest";
import type { AnimeListQuery } from "../api/types";
import {
  browseHref,
  browseHrefFromApiLink,
  parseBrowseQuery,
  toSearchParams,
  withParam,
  withoutFilters,
} from "./query";

const FULL: AnimeListQuery = {
  q: "shippuden",
  franchise: 1,
  status: "FINISHED",
  format: "TV",
  year_from: 2000,
  year_to: 2010,
  min_score: 7.5,
  on_watchlist: true,
  watchlist_status: "watching",
  sort: "-score",
  page: 2,
  page_size: 48,
};

describe("URL ⇄ query", () => {
  it("round-trips every parameter of listAnime", () => {
    expect(parseBrowseQuery(toSearchParams(FULL))).toEqual(FULL);
    expect(browseHref(FULL)).toBe(
      "/anime?q=shippuden&franchise=1&status=FINISHED&format=TV&year_from=2000&year_to=2010&min_score=7.5&on_watchlist=true&watchlist_status=watching&sort=-score&page=2&page_size=48",
    );
  });

  it("reads the links the Universe page emits", () => {
    expect(parseBrowseQuery("franchise=4")).toEqual({ franchise: 4 });
    expect(parseBrowseQuery("status=RELEASING")).toEqual({ status: "RELEASING" });
    expect(parseBrowseQuery("status=NOT_YET_RELEASED")).toEqual({ status: "NOT_YET_RELEASED" });
    expect(parseBrowseQuery("watchlist_status=watching")).toEqual({ watchlist_status: "watching" });
    expect(parseBrowseQuery("on_watchlist=false")).toEqual({ on_watchlist: false });
  });

  it("ignores junk values and unknown parameters instead of sending them", () => {
    expect(
      parseBrowseQuery(
        "franchise=abc&status=AIRING&format=tv&year_from=20x5&year_to=&min_score=lots&on_watchlist=yes" +
          "&watchlist_status=WATCHING&sort=random&page=two&page_size=1e3&q=%20%20&utm_source=x",
      ),
    ).toEqual({});
  });

  it("keeps well-shaped values even when out of range: the API judges ranges", () => {
    expect(parseBrowseQuery("year_from=2010&year_to=2000&page=0&min_score=11")).toEqual({
      year_from: 2010,
      year_to: 2000,
      min_score: 11,
      page: 0,
    });
  });

  it("goes back to page 1 when a filter changes, and keeps sort and size on clear", () => {
    expect(withParam(FULL, "format", "MOVIE").page).toBeUndefined();
    expect(withParam(FULL, "page", 3).page).toBe(3);
    expect(withParam({ franchise: 1 }, "franchise", undefined)).toEqual({});
    expect(withoutFilters(FULL)).toEqual({ sort: "-score", page_size: 48 });
  });

  it("turns the API's page links into Browse URLs, exactly as given", () => {
    expect(browseHrefFromApiLink("/v1/anime?franchise=1&sort=-popularity&page=2&page_size=2")).toBe(
      "/anime?franchise=1&sort=-popularity&page=2&page_size=2",
    );
    expect(parseBrowseQuery(new URL(browseHrefFromApiLink("/v1/anime?page=3&page_size=24"), "http://x").search)).toEqual({
      page: 3,
      page_size: 24,
    });
  });
});
