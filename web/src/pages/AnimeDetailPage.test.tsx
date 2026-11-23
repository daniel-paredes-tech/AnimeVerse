import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnimeDetail, Problem, ValidationProblem, WatchlistEntry } from "../api/types";
import { routes } from "../routes";

// The contract's AnimeDetail example.
const naruto: AnimeDetail = {
  id: 1,
  anilist_id: 20,
  mal_id: 20,
  title: "NARUTO",
  title_english: "Naruto",
  title_japanese: "NARUTO -ナルト-",
  format: "TV",
  status: "FINISHED",
  episodes: 220,
  start_year: 2002,
  end_year: 2007,
  aired_from: "2002-10-03",
  aired_to: "2007-02-08",
  score: 8.0,
  popularity: 743139,
  synopsis: "Naruto Uzumaki, a hyperactive and knuckle-headed ninja, lives in Konohagakure...",
  image_url: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/bx20-dE6UHbFFg1A5.jpg",
  anilist_url: "https://anilist.co/anime/20",
  franchises: [{ id: 1, name: "Naruto" }],
  watchlist_entry: null,
  updated_at: "2026-11-21T12:24:31Z",
};

const unknownish: AnimeDetail = {
  ...naruto,
  id: 2,
  mal_id: null,
  title: "THE ONE PIECE",
  title_english: null,
  title_japanese: null,
  format: null,
  status: null,
  episodes: null,
  start_year: null,
  end_year: null,
  aired_from: null,
  aired_to: null,
  score: null,
  popularity: null,
  synopsis: null,
  image_url: null,
  anilist_url: null,
  franchises: [],
};

const entry: WatchlistEntry = {
  anime_id: 1,
  status: "watching",
  episodes_watched: 110,
  rating: 9,
  notes: "Rewatch the Chunin exam arc.",
  created_at: "2026-11-23T18:00:00Z",
  updated_at: "2026-11-23T18:00:00Z",
};

interface Call {
  method: string;
  path: string;
  body: unknown;
}

type Handler = (call: Call) => { status: number; body?: unknown };

function setup(path: string, handler: Handler) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const request = input instanceof Request ? input : new Request(input);
      const url = new URL(request.url);
      const text = request.method === "GET" || request.method === "DELETE" ? "" : await request.clone().text();
      const call = { method: request.method, path: url.pathname, body: text ? JSON.parse(text) : undefined };
      calls.push(call);
      if (url.pathname === "/v1/franchises") return Response.json({ data: [{ id: 1, name: "Naruto", anime_count: 26 }] });
      const { status, body } = handler(call);
      return new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: body === undefined ? {} : { "Content-Type": status >= 400 ? "application/problem+json" : "application/json" },
      });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
  return { calls, writes: () => calls.filter((c) => c.method !== "GET") };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Detail page", () => {
  it("shows every field, with links to the franchise and to AniList", async () => {
    setup("/anime/1", () => ({ status: 200, body: naruto }));
    expect(await screen.findByRole("heading", { level: 1, name: "NARUTO" })).toBeInTheDocument();
    expect(screen.getByText("NARUTO -ナルト-")).toHaveAttribute("lang", "ja");
    expect(screen.getByRole("link", { name: "Naruto" })).toHaveAttribute("href", "/anime?franchise=1");
    const anilist = screen.getByRole("link", { name: /Open its AniList page/ });
    expect(anilist).toHaveAttribute("href", "https://anilist.co/anime/20");
    expect(anilist).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("3 October 2002 to 8 February 2007")).toBeInTheDocument();
    expect(screen.getByText("Score 8.0 / 10")).toBeInTheDocument();
    expect(screen.getByText("of 220 episodes")).toBeInTheDocument();
  });

  it("says every unknown out loud", async () => {
    setup("/anime/2", () => ({ status: 200, body: unknownish }));
    await screen.findByRole("heading", { level: 1, name: "THE ONE PIECE" });
    for (const text of [
      "No English title",
      "No native title",
      "No franchise",
      "Unscored",
      "Format unknown",
      "Release status unknown",
      "Start year unknown",
      "Unknown or not ended",
      "Air dates unknown",
      "AniList page unknown",
      "No synopsis.",
      "No cover image",
      "episode count unknown",
    ]) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
  });

  it("designs the API's 404 for an id that doesn't exist", async () => {
    const notFound: Problem = {
      type: "urn:animeverse:problem:not-found",
      title: "Resource not found",
      status: 404,
      detail: "There is no anime with id 9999.",
      instance: "/v1/anime/9999",
    };
    setup("/anime/9999", () => ({ status: 404, body: notFound }));
    expect(await screen.findByRole("heading", { level: 1, name: "This anime isn't in the catalogue" })).toBeInTheDocument();
    expect(screen.getByText(/There is no anime with id 9999\./)).toBeInTheDocument();
  });
});

describe("Watchlist postcard", () => {
  it("PUTs the contract's exact body, nulls included, and stamps only after a 201", async () => {
    const { writes } = setup("/anime/1", (call) =>
      call.method === "PUT"
        ? { status: 201, body: { ...entry, status: "planning", episodes_watched: 0, rating: null, notes: null } }
        : { status: 200, body: naruto },
    );
    await screen.findByRole("heading", { name: "Your watchlist" });
    expect(screen.getByText("Not on your watchlist.")).toBeInTheDocument();
    expect(document.querySelector(".stamp")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Add to watchlist" }));
    expect(await screen.findByText("Added to your watchlist.")).toBeInTheDocument();
    expect(writes()).toEqual([
      {
        method: "PUT",
        path: "/v1/anime/1/watchlist-entry",
        body: { status: "planning", episodes_watched: 0, rating: null, notes: null },
      },
    ]);
    expect(document.querySelector(".stamp")).toHaveTextContent("Added");
  });

  it("pre-fills from the existing entry and says 'updated' on a 200", async () => {
    const { writes } = setup("/anime/1", (call) =>
      call.method === "PUT"
        ? { status: 200, body: { ...entry, episodes_watched: 111, updated_at: "2026-11-24T08:00:00Z" } }
        : { status: 200, body: { ...naruto, watchlist_entry: entry } },
    );
    const episodes = await screen.findByLabelText("Episodes watched");
    expect(episodes).toHaveValue(110);
    expect(screen.getByRole("radio", { name: "Watching" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "9" })).toBeChecked();
    expect(screen.getByLabelText("Notes")).toHaveValue("Rewatch the Chunin exam arc.");

    await userEvent.click(screen.getByRole("button", { name: "One episode more" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Your watchlist entry was updated.")).toBeInTheDocument();
    expect(writes()[0]!.body).toEqual({
      status: "watching",
      episodes_watched: 111,
      rating: 9,
      notes: "Rewatch the Chunin exam arc.",
    });
    expect(document.querySelector(".stamp")).toHaveTextContent("Updated");
  });

  it("shows the API's 422 next to each field, focuses the first, and lists the rest at the top", async () => {
    const refused: ValidationProblem = {
      type: "urn:animeverse:problem:validation-error",
      title: "Validation failed",
      status: 422,
      detail: "The watchlist entry breaks 3 rules.",
      instance: "/v1/anime/1/watchlist-entry",
      errors: [
        { location: "body", field: "episodes_watched", code: "exceeds_episodes", message: "Can't be more than the anime's 220 episodes." },
        { location: "body", field: "status", code: "completed_requires_all_episodes", message: "Completed needs all 220 episodes watched." },
        { location: "body", field: "", code: "invalid_json", message: "Something about the body as a whole." },
      ],
    };
    setup("/anime/1", (call) => (call.method === "PUT" ? { status: 422, body: refused } : { status: 200, body: naruto }));
    const episodes = await screen.findByLabelText("Episodes watched");
    await userEvent.click(screen.getByRole("radio", { name: "Completed" }));
    await userEvent.clear(episodes);
    await userEvent.type(episodes, "300");
    await userEvent.click(screen.getByRole("button", { name: "Add to watchlist" }));

    const statusGroup = await screen.findByRole("radiogroup", { name: "Status" });
    expect(statusGroup).toHaveAttribute("aria-invalid", "true");
    expect(statusGroup).toHaveAccessibleDescription("Completed needs all 220 episodes watched.");
    expect(episodes).toHaveAttribute("aria-invalid", "true");
    expect(episodes).toHaveAccessibleDescription(/Can't be more than the anime's 220 episodes\./);
    // Status comes first in the form, so its checked radio gets focus.
    await waitFor(() => expect(screen.getByRole("radio", { name: "Completed" })).toHaveFocus());
    const summary = screen.getByRole("alert");
    expect(summary).toHaveTextContent("The watchlist entry breaks 3 rules.");
    expect(summary).toHaveTextContent("Something about the body as a whole.");
    expect(summary).not.toHaveTextContent("Can't be more than");
    // Nothing was saved, so no stamp, and the typed values stay.
    expect(document.querySelector(".stamp")).toBeNull();
    expect(episodes).toHaveValue(300);
  });

  it("treats a 404 on delete as already removed", async () => {
    setup("/anime/1", (call) =>
      call.method === "DELETE"
        ? {
            status: 404,
            body: {
              type: "urn:animeverse:problem:not-found",
              title: "Resource not found",
              status: 404,
              detail: "Anime 1 is not on your watchlist.",
              instance: "/v1/anime/1/watchlist-entry",
            },
          }
        : { status: 200, body: { ...naruto, watchlist_entry: entry } },
    );
    await userEvent.click(await screen.findByRole("button", { name: "Remove from watchlist" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, remove it" }));
    expect(
      await screen.findByText("It was already off your watchlist (Anime 1 is not on your watchlist.)."),
    ).toBeInTheDocument();
    expect(screen.getByText("Not on your watchlist.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("removes after a confirmation step", async () => {
    let deletes = 0;
    const { writes } = setup("/anime/1", (call) => {
      if (call.method === "DELETE") {
        deletes += 1;
        return deletes === 1
          ? { status: 204 }
          : {
              status: 404,
              body: {
                type: "urn:animeverse:problem:not-found",
                title: "Resource not found",
                status: 404,
                detail: "Anime 1 is not on your watchlist.",
                instance: "/v1/anime/1/watchlist-entry",
              },
            };
      }
      return { status: 200, body: { ...naruto, watchlist_entry: entry } };
    });
    await userEvent.click(await screen.findByRole("button", { name: "Remove from watchlist" }));
    const confirm = screen.getByRole("group", { name: /Remove NARUTO from your watchlist\?/ });
    await waitFor(() => expect(within(confirm).getByRole("button", { name: "Keep it" })).toHaveFocus());
    expect(writes()).toHaveLength(0);

    await userEvent.click(within(confirm).getByRole("button", { name: "Yes, remove it" }));
    expect(await screen.findByText("Removed from your watchlist.")).toBeInTheDocument();
    expect(writes()).toEqual([{ method: "DELETE", path: "/v1/anime/1/watchlist-entry", body: undefined }]);
    expect(screen.getByText("Not on your watchlist.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add to watchlist" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove from watchlist" })).toBeNull();
  });
});
