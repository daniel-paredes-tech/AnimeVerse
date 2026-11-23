import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnimePage, AnimeSummary, ValidationProblem } from "../api/types";
import { routes } from "../routes";

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

const special: AnimeSummary = {
  ...naruto,
  id: 9,
  anilist_id: 99,
  title: "Some Special",
  title_english: null,
  title_japanese: null,
  format: null,
  status: null,
  episodes: null,
  start_year: null,
  score: null,
  popularity: null,
  image_url: null,
};

function page(data: AnimeSummary[], meta: AnimePage["meta"], links: AnimePage["links"]): AnimePage {
  return { data, meta, links };
}

/** Shaped exactly like the contract's ValidationProblem (here, the year rule). */
const yearProblem: ValidationProblem = {
  type: "urn:animeverse:problem:invalid-request",
  title: "Invalid request",
  status: 400,
  detail: "The request has 1 invalid parameter.",
  instance: "/v1/anime",
  errors: [{ location: "query", field: "year_to", code: "too_small", message: "Must not be less than year_from (2010)." }],
};

type Responder = (url: URL) => { status: number; body: unknown };

function setup(path: string, respond: Responder) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    if (url.pathname === "/v1/franchises") {
      return Response.json({ data: [{ id: 1, name: "Naruto", anime_count: 26 }] });
    }
    const { status, body } = respond(url);
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": status >= 400 ? "application/problem+json" : "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  const animeCalls = () =>
    fetchMock.mock.calls
      .map(([input]) => new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url))
      .filter((u) => u.pathname === "/v1/anime");
  return { router, animeCalls };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BrowsePage", () => {
  it("sends the URL's filters to the API and shows every null as unknown", async () => {
    const { animeCalls } = setup("/anime?franchise=1&format=TV&sort=-score&junk=1", () => ({
      status: 200,
      body: page([naruto, special], { page: 1, page_size: 24, total_items: 2, total_pages: 1 }, {
        self: "/v1/anime?franchise=1&format=TV&sort=-score&page=1&page_size=24",
        next: null,
        prev: null,
      }),
    }));
    expect(await screen.findByText("2 anime match · page 1 of 1")).toBeInTheDocument();
    const sent = animeCalls()[0]!;
    expect(Object.fromEntries(sent.searchParams)).toEqual({ franchise: "1", format: "TV", sort: "-score" });

    const card = screen.getByRole("article", { name: "Some Special" });
    expect(within(card).getByText("No English title")).toBeInTheDocument();
    expect(within(card).getByText("Unscored")).toBeInTheDocument();
    expect(within(card).getAllByText("Unknown")).toHaveLength(5);
    expect(within(card).getByRole("link", { name: "Some Special" })).toHaveAttribute("href", "/anime/9");
    expect(screen.getByLabelText("Franchise")).toHaveValue("1");
    expect(screen.getByLabelText("Order")).toHaveValue("-score");
  });

  it("puts each 400 field error next to its own control", async () => {
    setup("/anime?year_from=2010&year_to=2000", () => ({ status: 400, body: yearProblem }));
    const message = await screen.findByText("Must not be less than year_from (2010).");
    const yearTo = screen.getByLabelText("to");
    expect(yearTo).toHaveAttribute("aria-invalid", "true");
    expect(yearTo).toHaveAccessibleDescription("Must not be less than year_from (2010).");
    expect(message.closest(".balloon")).toHaveAttribute("id", "filter-year_to-errors");
    expect(screen.getByLabelText("From")).not.toHaveAttribute("aria-invalid");
    // The rest of the problem is shown too, in the results area.
    expect(screen.getByRole("alert")).toHaveTextContent("The request has 1 invalid parameter.");
  });

  it("shows the empty state with a one-click clear-all", async () => {
    const { router, animeCalls } = setup("/anime?q=zzz&format=MUSIC", (url) =>
      url.searchParams.has("q")
        ? { status: 200, body: page([], { page: 1, page_size: 24, total_items: 0, total_pages: 0 }, { self: "/v1/anime?q=zzz", next: null, prev: null }) }
        : { status: 200, body: page([naruto], { page: 1, page_size: 24, total_items: 1, total_pages: 1 }, { self: "/v1/anime", next: null, prev: null }) },
    );
    expect(await screen.findByText("No anime match these filters")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove filter: Title contains “zzz”" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear all filters" }));
    expect(router.state.location.search).toBe("");
    expect(await screen.findByText("1 anime matches · page 1 of 1")).toBeInTheDocument();
    expect(animeCalls().at(-1)!.search).toBe("");
  });

  it("designs the page past the end, with a way back to page 1", async () => {
    setup("/anime?franchise=1&page=9", () => ({
      status: 200,
      body: page([], { page: 9, page_size: 24, total_items: 26, total_pages: 2 }, {
        self: "/v1/anime?franchise=1&sort=-popularity&page=9&page_size=24",
        next: null,
        prev: "/v1/anime?franchise=1&sort=-popularity&page=8&page_size=24",
      }),
    }));
    expect(await screen.findByText("Page 9 is past the end")).toBeInTheDocument();
    expect(screen.getByText("These filters match 26 anime on 2 pages.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to page 1" })).toHaveAttribute("href", "/anime?franchise=1");
  });

  it("pages by following the API's links.next and links.prev as given", async () => {
    const first = page([naruto], { page: 1, page_size: 1, total_items: 2, total_pages: 2 }, {
      self: "/v1/anime?franchise=1&sort=-popularity&page=1&page_size=1",
      next: "/v1/anime?franchise=1&sort=-popularity&page=2&page_size=1",
      prev: null,
    });
    const second = page([special], { page: 2, page_size: 1, total_items: 2, total_pages: 2 }, {
      self: "/v1/anime?franchise=1&sort=-popularity&page=2&page_size=1",
      next: null,
      prev: "/v1/anime?franchise=1&sort=-popularity&page=1&page_size=1",
    });
    const { router, animeCalls } = setup("/anime?franchise=1&page_size=1", (url) => ({
      status: 200,
      body: url.searchParams.get("page") === "2" ? second : first,
    }));
    await screen.findByText("2 anime match · page 1 of 2");
    expect(screen.getByText("Previous page")).toHaveAttribute("aria-disabled", "true");

    await userEvent.click(screen.getByRole("link", { name: "Next page" }));
    expect(router.state.location.search).toBe("?franchise=1&sort=-popularity&page=2&page_size=1");
    await screen.findByText("2 anime match · page 2 of 2");
    expect(Object.fromEntries(animeCalls().at(-1)!.searchParams)).toEqual({
      franchise: "1",
      sort: "-popularity",
      page: "2",
      page_size: "1",
    });

    expect(screen.getByRole("link", { name: "Previous page" })).toHaveAttribute(
      "href",
      "/anime?franchise=1&sort=-popularity&page=1&page_size=1",
    );
  });

  it("changing a filter writes it to the URL and goes back to page 1", async () => {
    const { router } = setup("/anime?page=2", () => ({
      status: 200,
      body: page([naruto], { page: 1, page_size: 24, total_items: 1, total_pages: 1 }, { self: "/v1/anime", next: null, prev: null }),
    }));
    await screen.findByText(/anime match/);
    await userEvent.selectOptions(screen.getByLabelText("Release status"), "RELEASING");
    expect(router.state.location.search).toBe("?status=RELEASING");
  });
});
