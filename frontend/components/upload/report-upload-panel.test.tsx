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
    expect(screen.getByRole("button", { name: "开始新演示" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看已有结果" }));

    expect(router.push).toHaveBeenCalledWith("/reports/report-existing/dashboard");
  });

  it("requires confirmation before clearing and re-uploading the selected report", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(duplicateReportResponse())
      .mockResolvedValueOnce(
        jsonResponse({ cleared_report_count: 1, cleared_runtime_directories: ["uploads", "derived"] }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ report_id: "report-new", original_filename: "report.pdf", file_hash: "hash-new", status: "uploaded" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    await selectAndUploadDuplicate();

    fireEvent.click(screen.getByRole("button", { name: "开始新演示" }));

    expect(screen.getByText("这会清除演示库中的报告、复核、整改任务和输出版本。")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "确认清空并重新上传" }));

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/reports/report-new/confirm"));
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://localhost:8000/api/demo/reset");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({ confirmation: "RESET_DEMO" });
  });

  it("explains when an active analysis blocks demo reset", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(duplicateReportResponse())
        .mockResolvedValueOnce(
          jsonResponse(
            { detail: { code: "demo_reset_blocked_active_run", run_id: "run-active" } },
            409,
          ),
        ),
    );
    await selectAndUploadDuplicate();

    fireEvent.click(screen.getByRole("button", { name: "开始新演示" }));
    fireEvent.click(screen.getByRole("button", { name: "确认清空并重新上传" }));

    expect(await screen.findByText("当前报告仍在分析，无法清空演示库。请等待分析结束后重试。")).toBeInTheDocument();
    expect(screen.queryByText("demo_reset_blocked_active_run")).not.toBeInTheDocument();
  });

  it("distinguishes a reset network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(duplicateReportResponse())
        .mockRejectedValueOnce(new TypeError("network unavailable")),
    );
    await selectAndUploadDuplicate();

    fireEvent.click(screen.getByRole("button", { name: "开始新演示" }));
    fireEvent.click(screen.getByRole("button", { name: "确认清空并重新上传" }));

    expect(await screen.findByText("清空演示库失败，请检查后端服务后重试。")).toBeInTheDocument();
  });

  it("distinguishes re-upload failure after reset succeeds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(duplicateReportResponse())
        .mockResolvedValueOnce(
          jsonResponse({ cleared_report_count: 1, cleared_runtime_directories: ["uploads", "derived"] }),
        )
        .mockResolvedValueOnce(
          jsonResponse({ detail: { code: "upload_failed" } }, 500),
        ),
    );
    await selectAndUploadDuplicate();

    fireEvent.click(screen.getByRole("button", { name: "开始新演示" }));
    fireEvent.click(screen.getByRole("button", { name: "确认清空并重新上传" }));

    expect(
      await screen.findByText("演示库已清空，但重新上传报告失败，请重新选择文件后再试。"),
    ).toBeInTheDocument();
  });
});
