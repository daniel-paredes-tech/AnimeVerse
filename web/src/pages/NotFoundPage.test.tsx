import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { routes } from "../routes";
import { createQueryClient } from "../api/hooks";
import { parseAnimeId } from "./AnimeDetailPage";

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("NotFoundPage", () => {
  it("renders for an unknown path, with a way back to the universe", () => {
    renderAt("/no/such/page");
    expect(screen.getByRole("heading", { level: 1, name: "This page isn't in this week's issue" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the universe" })).toHaveAttribute("href", "/");
    // The shell stays: masthead nav and the AniList credit.
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "AniList" })).toHaveAttribute("href", "https://anilist.co");
  });

  it("renders for an anime id the contract can't accept", () => {
    renderAt("/anime/abc");
    expect(screen.getByRole("heading", { level: 1, name: "This page isn't in this week's issue" })).toBeInTheDocument();
  });
});

describe("parseAnimeId", () => {
  it("accepts only ids from 1 to 2147483647", () => {
    expect(parseAnimeId("1")).toBe(1);
    expect(parseAnimeId("2147483647")).toBe(2147483647);
    expect(parseAnimeId("2147483648")).toBeNull();
    expect(parseAnimeId("0")).toBeNull();
    expect(parseAnimeId("01")).toBeNull();
    expect(parseAnimeId("-3")).toBeNull();
    expect(parseAnimeId(undefined)).toBeNull();
  });
});
