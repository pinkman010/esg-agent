import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportMetadataConfirmation } from "./report-metadata-confirmation";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
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
      metadata_detected: { report_year: 2024, language: "zh-CN" },
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

    fireEvent.change(await screen.findByLabelText("企业名称"), { target: { value: "测试公司" } });
    fireEvent.click(screen.getByRole("button", { name: "确认报告信息" }));
    expect(await screen.findByText("报告信息已确认")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "启动分析" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/reports/report-1/progress?runId=run-1"));
  });
});
