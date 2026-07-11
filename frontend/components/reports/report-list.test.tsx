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
    expect(screen.getByText("待启动分析")).toBeInTheDocument();
  });
});
