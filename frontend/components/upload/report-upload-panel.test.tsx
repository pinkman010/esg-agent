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

  it("uploads a PDF and opens metadata confirmation", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse({ report_id: "report-1", original_filename: "report.pdf", file_hash: "hash-1", status: "uploaded" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ReportUploadPanel />);

    const file = new File(["pdf"], "report.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("PDF 报告文件"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "上传 PDF" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/reports/report-1/confirm"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
