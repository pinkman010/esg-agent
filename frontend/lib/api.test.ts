import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, listRuns } from "./api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the default backend URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await listRuns();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/runs");
  });

  it("throws a typed error for non-2xx responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "bad request" }, 400)));

    await expect(listRuns()).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      body: { detail: "bad request" },
    });
  });
});