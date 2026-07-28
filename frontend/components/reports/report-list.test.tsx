import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportList } from "./report-list";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

describe("ReportList", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the first-use empty state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ items: [], page: 1, page_size: 50, total: 0 })));

    renderWithQuery(<ReportList />);

    expect(await screen.findByText("尚未上传 ESG 报告")).toBeInTheDocument();
  });

  it("shows existing reports with business status labels", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      items: [{
        report_id: "report-1",
        original_filename: "测试公司 ESG 报告.pdf",
        file_hash: "hash-1",
        page_count: 78,
        company_name: "测试公司",
        report_year: 2024,
        language: "zh-CN",
        status: "ready_for_analysis",
        metadata_detected: {},
        metadata_confirmed_at: "2026-07-11T00:00:00Z",
        created_at: "2026-07-11T00:00:00Z",
        updated_at: "2026-07-11T00:00:00Z",
      }],
      page: 1,
      page_size: 50,
      total: 1,
    })));

    renderWithQuery(<ReportList />);

    expect(await screen.findByText("测试公司")).toBeInTheDocument();
    expect(screen.getByText("2024 年")).toBeInTheDocument();
    expect(screen.getByText(/创建于 2026/)).toBeInTheDocument();
    expect(screen.getByText("zh-CN")).toBeInTheDocument();
    expect(screen.getByText("78 页")).toBeInTheDocument();
    expect(screen.getByText("ID report-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /待启动分析/ })).toHaveAttribute(
      "href",
      "/reports/report-1/confirm",
    );
  });

  it("keeps report instances identifiable when optional metadata is missing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      items: [{
        report_id: "report-1234567890abcdef",
        original_filename: "测试公司 ESG 报告.pdf",
        file_hash: "hash-1",
        page_count: null,
        company_name: "测试公司",
        report_year: 2024,
        language: null,
        status: "ready_for_analysis",
        metadata_detected: {},
        metadata_confirmed_at: null,
        created_at: null,
        updated_at: null,
      }],
      page: 1,
      page_size: 50,
      total: 1,
    })));

    renderWithQuery(<ReportList />);

    expect(await screen.findByText("创建时间待记录")).toBeInTheDocument();
    expect(screen.getByText("语言待确认")).toBeInTheDocument();
    expect(screen.getByText("页数待确认")).toBeInTheDocument();
    expect(screen.getByText("ID 12345678")).toBeInTheDocument();
  });

  it("uses review-priority wording for the completed review status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      items: [{
        report_id: "report-2",
        original_filename: "测试公司 ESG 报告.pdf",
        file_hash: "hash-2",
        page_count: 78,
        company_name: "测试公司",
        report_year: 2024,
        language: "zh-CN",
        status: "high_risk_review_completed",
        metadata_detected: {},
        metadata_confirmed_at: "2026-07-11T00:00:00Z",
        created_at: "2026-07-11T00:00:00Z",
        updated_at: "2026-07-11T00:00:00Z",
      }],
      page: 1,
      page_size: 50,
      total: 1,
    })));

    renderWithQuery(<ReportList />);

    expect(await screen.findByRole("link", { name: /高优先级复核已完成/ })).toHaveAttribute(
      "href",
      "/reports/report-2/dashboard",
    );
  });

  it("opens the active run for an analyzing report", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/reports?")) {
        return Promise.resolve(jsonResponse({
          items: [{
            report_id: "report-running",
            original_filename: "远景能源 2024 ESG 报告.pdf",
            file_hash: "hash-running",
            page_count: 78,
            company_name: "远景能源有限公司",
            report_year: 2024,
            language: "zh-CN",
            status: "analyzing",
            metadata_detected: {},
            metadata_confirmed_at: "2026-07-11T00:00:00Z",
            created_at: "2026-07-11T00:00:00Z",
            updated_at: "2026-07-11T00:00:00Z",
          }],
          page: 1,
          page_size: 50,
          total: 1,
        }));
      }
      if (url.endsWith("/api/runs")) {
        return Promise.resolve(jsonResponse([{
          run_id: "run-active",
          report_id: "report-running",
          status: "running",
          confirm_llm: false,
        }]));
      }
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<ReportList />);

    expect(await screen.findByRole("link", { name: /查看分析进度/ })).toHaveAttribute(
      "href",
      "/reports/report-running/progress?runId=run-active",
    );
  });
});
