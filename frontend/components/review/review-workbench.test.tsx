import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReviewWorkbench } from "./review-workbench";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("ReviewWorkbench", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows an empty state when no runs need review", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithQuery(<ReviewWorkbench />);

    expect(await screen.findByText("No runs need manual review.")).toBeInTheDocument();
  });
});