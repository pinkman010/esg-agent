import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportUploadPanel } from "./report-upload-panel";

const router = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("ReportUploadPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    router.push.mockReset();
  });

  it("uploads a PDF, shows report metadata, and starts analysis", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ report_id: "report-1", original_filename: "report.pdf", file_hash: "hash-1", status: "uploaded" }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ run_id: "run-1", report_id: "report-1", status: "completed", confirm_llm: true, error_message: null }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ReportUploadPanel />);

    const file = new File(["pdf"], "report.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("PDF report"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));

    expect(await screen.findByText("report-1")).toBeInTheDocument();
    expect(screen.getByText("hash-1")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Allow external model call"));
    fireEvent.click(screen.getByRole("button", { name: "Start analysis" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/runs/run-1"));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});