import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/errors";
import { ProblemView } from "./states";

describe("ProblemView", () => {
  it("shows the problem's title and detail, and how to start the database on 503", async () => {
    const retry = vi.fn();
    const error = new ApiError(503, {
      type: "urn:animeverse:problem:service-unavailable",
      title: "Service unavailable",
      status: 503,
      detail: "The database is unavailable. Try again later.",
      instance: "/v1/anime",
    });
    render(<ProblemView error={error} onRetry={retry} />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Service unavailable")).toBeInTheDocument();
    expect(screen.getByText("The database is unavailable. Try again later.")).toBeInTheDocument();
    expect(screen.getByText("docker compose up -d")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("doesn't mention docker for other problems", () => {
    const error = new ApiError(404, {
      type: "urn:animeverse:problem:not-found",
      title: "Resource not found",
      status: 404,
      detail: "There is no anime with id 9999.",
      instance: "/v1/anime/9999",
    });
    render(<ProblemView error={error} />);
    expect(screen.getByText("Resource not found")).toBeInTheDocument();
    expect(screen.getByText("There is no anime with id 9999.")).toBeInTheDocument();
    expect(screen.queryByText("docker compose up -d")).not.toBeInTheDocument();
  });

  it("explains an unreachable API", () => {
    render(<ProblemView error={new ApiError(null, null, "The API could not be reached.")} />);
    expect(screen.getByText("The API isn't answering")).toBeInTheDocument();
    expect(screen.getByText("animeverse serve")).toBeInTheDocument();
  });
});
