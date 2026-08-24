import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { HomeWorkspace } from "./home-workspace";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const report = {
  report_id: "report-1",
  original_filename: "Envision Energy 2024-zh.pdf",
  file_hash: "hash-1",
  page_count: 78,
  company_name: "远景能源有限公司",
  report_year: 2024,
  language: "zh-CN",
  status: "analysis_completed",
  metadata_detected: {},
  metadata_confirmed_at: "2026-07-26T00:00:00Z",
  created_at: "2026-07-26T00:00:00Z",
  updated_at: "2026-07-26T00:00:00Z",
};

describe("HomeWorkspace", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the first-use path without inventing a report", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      items: [],
      page: 1,
      page_size: 1,
      total: 0,
    })));

    const { container } = renderWithQuery(<HomeWorkspace />);

    expect(await screen.findByText("从第一份 ESG 报告开始")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "上传第一份报告" })).toHaveAttribute("href", "/reports");
    expect(screen.queryByText("577")).not.toBeInTheDocument();
    const heroArtwork = container.querySelector('img[src*="overview-dashboard-hero"]');
    expect(heroArtwork).toHaveClass("opacity-[0.28]");
    expect(heroArtwork?.nextElementSibling).toHaveClass(
      "bg-[linear-gradient(90deg,rgba(255,255,255,0.82)_0%,rgba(236,253,245,0.54)_52%,rgba(209,250,229,0.28)_100%)]",
    );
  });

  it("presents the latest completed report with API-backed metrics", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ items: [report], page: 1, page_size: 1, total: 1 }))
      .mockResolvedValueOnce(jsonResponse({
        report_id: "report-1",
        run_id: "run-1",
        standard_unit_count: 577,
        verdict_counts: { disclosed: 36, partially_disclosed: 154, unknown: 309 },
        risk_counts: { high: 9, medium: 54, low: 436 },
        review_priority_counts: { high: 9, medium: 54, low: 436 },
        high_risk_total: 9,
        high_risk_reviewed: 0,
        high_priority_total: 9,
        high_priority_reviewed: 0,
        high_priority_unresolved: 9,
        applicability_counts: { applicable: 190, undetermined: 309 },
        applicability_undetermined_total: 309,
        failed_requirement_count: 0,
      }));
    vi.stubGlobal("fetch", fetchMock);

    const { container } = renderWithQuery(<HomeWorkspace />);

    expect(await screen.findByText("远景能源有限公司 · 2024 年")).toBeInTheDocument();
    expect(await screen.findByText("577")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("54")).toBeInTheDocument();
    expect(screen.getByText("436")).toBeInTheDocument();
    expect(screen.getByText("309")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看报告总览" })).toHaveAttribute(
      "href",
      "/reports/report-1/dashboard",
    );
    expect(screen.getByRole("link", { name: "进入三栏复核" })).toHaveAttribute(
      "href",
      "/reports/report-1/review",
    );
    expect(screen.getByText("AI 输出仅供分析辅助，不替代 ESG 专业判断或最终合规结论。")).toBeInTheDocument();
    expect(screen.queryByText(/499|78 个上下文|6 个方法|16 条差异/)).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("page_size=1"), expect.anything());
    const heroArtwork = container.querySelector('img[src*="overview-dashboard-hero"]');
    expect(heroArtwork).toHaveClass("opacity-[0.25]");
    expect(heroArtwork?.nextElementSibling).toHaveClass(
      "bg-[linear-gradient(90deg,rgba(255,255,255,0.84)_0%,rgba(236,253,245,0.56)_52%,rgba(209,250,229,0.30)_100%)]",
    );
  });

  it("shows a retryable error instead of a blank workspace", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse({ items: [], page: 1, page_size: 1, total: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<HomeWorkspace />);

    expect(await screen.findByRole("alert")).toHaveTextContent("工作台数据加载失败");
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    expect(await screen.findByText("从第一份 ESG 报告开始")).toBeInTheDocument();
  });
});
