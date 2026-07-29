import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportContextNav } from "./report-context-nav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reports/report-1/dashboard",
}));


describe("ReportContextNav", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("links the current report workspace to its audit timeline", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({
        report_id: "report-1",
        original_filename: "report.pdf",
        file_hash: "hash-1",
        page_count: 10,
        company_name: "示例公司",
        report_year: 2025,
        language: "zh-CN",
        status: "analysis_completed",
        metadata_detected: {},
        metadata_confirmed_at: null,
        updated_at: null,
        reopened_at: null,
        reopen_reason: null,
        created_at: null,
      }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      },
    ))));

    renderWithQuery(<ReportContextNav />);

    expect(
      await screen.findByRole("link", { name: "审计时间线" }),
    ).toHaveAttribute("href", "/reports/report-1/audit");
  });
});
