import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnimePage, AnimeSummary, Franchise } from "../api/types";
import { routes } from "../routes";

const franchises: Franchise[] = [
  { id: 1, name: "Naruto", anime_count: 2 },
  { id: 4, name: "One Piece", anime_count: 1 },
];

function anime(id: number, overrides: Partial<AnimeSummary>): AnimeSummary {
  return {
    id,
    anilist_id: id * 10,
    title: `Anime ${id}`,
    title_english: null,
    title_japanese: null,
    format: "TV",
    status: "FINISHED",
    episodes: 12,
    start_year: 2000 + id,
    end_year: null,
    score: 7.5,
    popularity: 1000 * id,
    image_url: null,
    franchises: [{ id: 1, name: "Naruto" }],
    watchlist_entry: null,
    ...overrides,
  };
}

const catalogue: AnimeSummary[] = [
  anime(1, { title: "NARUTO", score: 8.0, popularity: 743139 }),
  anime(2, { title: "Unscored Special", score: null, format: null, start_year: null, popularity: null }),
  anime(3, {
    title: "ONE PIECE",
    status: "RELEASING",
    episodes: null,
    franchises: [{ id: 4, name: "One Piece" }],
    watchlist_entry: {
      anime_id: 3,
      status: "watching",
      episodes_watched: 12,
      rating: null,
      notes: null,
      created_at: "2026-11-23T18:00:00Z",
      updated_at: "2026-11-23T18:00:00Z",
    },
  }),
];

function pageOf(data: AnimeSummary[]): AnimePage {
  return {
    data,
    meta: { page: 1, page_size: 100, total_items: data.length, total_pages: data.length ? 1 : 0 },
    links: { self: "/v1/anime?page=1&page_size=100", next: null, prev: null },
  };
}

function respond(input: RequestInfo | URL): Response {
  const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
  const body =
    url.pathname === "/v1/franchises"
      ? { data: franchises }
      : url.searchParams.get("status") === "RELEASING"
        ? pageOf(catalogue.filter((a) => a.status === "RELEASING"))
        : url.searchParams.has("status") || url.searchParams.has("watchlist_status")
          ? pageOf(catalogue.filter((a) => a.watchlist_entry?.status === url.searchParams.get("watchlist_status")))
          : pageOf(catalogue);
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function renderUniverse() {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => respond(input)));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: ["/"] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UniversePage", () => {
  it("draws every anime as a named star link, unscored ones said out loud", async () => {
    renderUniverse();
    const map = await screen.findByRole("group", { name: /Universe map/ });
    const stars = within(map).getAllByRole("link");
    expect(stars).toHaveLength(catalogue.length);
    expect(within(map).getByRole("link", { name: "NARUTO, Naruto, score 8.0 of 10" })).toHaveAttribute(
      "href",
      "/anime/1",
    );
    expect(within(map).getByRole("link", { name: /^Unscored Special, Naruto, unscored/ })).toBeInTheDocument();
    expect(
      within(map).getByRole("link", { name: /^ONE PIECE, One Piece, score 7.5 of 10, watching, episode 12 of unknown/ }),
    ).toBeInTheDocument();
  });

  it("offers each franchise plate as a button", async () => {
    renderUniverse();
    expect(await screen.findByRole("button", { name: "Naruto: 2 anime. Zoom into this constellation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "One Piece: 1 anime. Zoom into this constellation" })).toBeInTheDocument();
  });

  it("shows the same anime as a table in list view", async () => {
    renderUniverse();
    await screen.findByRole("group", { name: /Universe map/ });
    await userEvent.click(screen.getByRole("button", { name: "List" }));
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(catalogue.length + 1);
    expect(within(table).getByText("Unscored")).toBeInTheDocument();
    expect(within(table).getByText("Format unknown")).toBeInTheDocument();
  });

  it("dims stars that don't match the filters instead of hiding them", async () => {
    renderUniverse();
    const map = await screen.findByRole("group", { name: /Universe map/ });
    await userEvent.click(screen.getByRole("button", { name: /^Releasing/ }));
    expect(within(map).getAllByRole("link")).toHaveLength(catalogue.length);
    expect(within(map).getByRole("link", { name: /^NARUTO.*does not match the filters$/ })).toBeInTheDocument();
    expect(screen.getByText(/1 of 3 anime match/)).toBeInTheDocument();
  });

  it("fills the side column from the list endpoint", async () => {
    renderUniverse();
    const airing = await screen.findByRole("region", { name: /Airing now/ });
    expect(await within(airing).findByRole("link", { name: "ONE PIECE" })).toHaveAttribute("href", "/anime/3");
  });
});
