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

function duplicateReportResponse() {
  return jsonResponse(
    {
      detail: {
        code: "duplicate_report",
        message: "相同报告已存在",
        report_id: "report-existing",
        existing_report_status: "analysis_completed",
        can_start_new_demo: true,
      },
    },
    409,
  );
}

async function selectAndUploadDuplicate() {
  renderWithQuery(<ReportUploadPanel />);
  const file = new File(["pdf"], "report.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("PDF 报告文件"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "上传 PDF" }));
  expect(await screen.findByText("报告已存在")).toBeInTheDocument();
  return file;
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

  it("offers to open the existing report after a duplicate upload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        jsonResponse(
          {
            detail: {
              code: "duplicate_report",
              message: "相同报告已存在",
              report_id: "report-existing",
              existing_report_status: "analysis_completed",
              can_start_new_demo: true,
            },
          },
          409,
        ),
      ),
    );

    renderWithQuery(<ReportUploadPanel />);

    const file = new File(["pdf"], "report.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("PDF 报告文件"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "上传 PDF" }));

    expect(await screen.findByText("报告已存在")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新上传并分析" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看已有结果" }));

    expect(router.push).toHaveBeenCalledWith("/reports/report-existing/dashboard");
  });

  it("creates a new report without clearing existing data after explicit confirmation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(duplicateReportResponse())
      .mockResolvedValueOnce(
        jsonResponse({ report_id: "report-new", original_filename: "report.pdf", file_hash: "hash-new", status: "uploaded" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    await selectAndUploadDuplicate();

    fireEvent.click(screen.getByRole("button", { name: "重新上传并分析" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/reports/report-new/confirm"));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://localhost:8000/api/reports/upload?duplicate_policy=create_new",
    );
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/demo/reset"))).toBe(false);
  });

  it("keeps the existing report intact when creating the new report fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(duplicateReportResponse())
        .mockResolvedValueOnce(
          jsonResponse({ detail: { code: "upload_failed" } }, 500),
        ),
    );
    await selectAndUploadDuplicate();

    fireEvent.click(screen.getByRole("button", { name: "重新上传并分析" }));

    expect(
      await screen.findByText("重新上传失败，已有报告和历史结果未受影响，请重试。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看已有结果" })).toBeInTheDocument();
  });
});
