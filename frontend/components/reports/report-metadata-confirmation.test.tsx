import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportMetadataConfirmation } from "./report-metadata-confirmation";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

function reportWithStatus(status: string) {
  return {
    report_id: "report-1",
    original_filename: "测试公司 2024 ESG 报告.pdf",
    file_hash: "hash-1",
    page_count: 78,
    company_name: "测试公司",
    report_year: 2024,
    language: "zh-CN",
    status,
    metadata_detected: { company_name: "测试公司", report_year: 2024, language: "zh-CN" },
    metadata_confirmed_at: "2026-07-15T00:00:00Z",
    created_at: null,
    updated_at: null,
  };
}

describe("ReportMetadataConfirmation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    router.push.mockReset();
  });

  it("confirms detected metadata before starting analysis", async () => {
    const report = {
      report_id: "report-1",
      original_filename: "测试公司 2024 ESG 报告.pdf",
      file_hash: "hash-1",
      page_count: 78,
      company_name: null,
      report_year: null,
      language: null,
      status: "uploaded",
      metadata_detected: { company_name: "远景能源有限公司", report_year: 2024, language: "zh-CN" },
      metadata_confirmed_at: null,
      created_at: null,
      updated_at: null,
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(report))
      .mockResolvedValueOnce(jsonResponse({ ...report, company_name: "测试公司", report_year: 2024, language: "zh-CN", status: "ready_for_analysis" }))
      .mockResolvedValueOnce(jsonResponse({ run_id: "run-1", report_id: "report-1", status: "completed", confirm_llm: false, error_message: null }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ReportMetadataConfirmation reportId="report-1" />);

    expect(await screen.findByLabelText("企业名称")).toHaveValue("远景能源有限公司");
    fireEvent.change(screen.getByLabelText("企业名称"), { target: { value: "测试公司" } });
    fireEvent.click(screen.getByRole("button", { name: "确认报告信息" }));
    expect(await screen.findByText("报告信息已确认")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "启动分析" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/reports/report-1/progress?runId=run-1"));
  });

  it.each(["analysis_completed", "partially_completed"])(
    "locks metadata writes and offers result paths for %s",
    async (status) => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse(reportWithStatus(status))));

      renderWithQuery(<ReportMetadataConfirmation reportId="report-1" />);

      expect(await screen.findByText("该报告已有分析结果")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "查看分析结果" })).toHaveAttribute(
        "href",
        "/reports/report-1/dashboard",
      );
      expect(screen.getByRole("link", { name: "进入高优先级复核" })).toHaveAttribute(
        "href",
        "/reports/report-1/review",
      );
      expect(screen.queryByRole("button", { name: "确认报告信息" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "启动分析" })).not.toBeInTheDocument();
      expect(screen.getByLabelText("企业名称")).toBeDisabled();
    },
  );

  it("shows analyzing state without metadata or analysis write buttons", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse(reportWithStatus("analyzing"))));

    renderWithQuery(<ReportMetadataConfirmation reportId="report-1" />);

    expect(await screen.findByText("分析正在进行")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认报告信息" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "启动分析" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("企业名称")).toBeDisabled();
  });
});
