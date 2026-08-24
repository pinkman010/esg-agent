import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportDashboard } from "./report-dashboard";

describe("ReportDashboard", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("separates review priority and applicability counts", async () => {
    vi.stubGlobal("fetch", vi.fn((input: string | URL | Request) => {
      const url = String(input);
      const body = url.includes("/api/runs/run-1")
        ? {
            run_id: "run-1",
            report_id: "report-1",
            status: "completed",
            confirm_llm: false,
            ai_summary: { succeeded: 0, failed: 0, skipped: 499 },
          }
        : {
            report_id: "report-1",
            run_id: "run-1",
            standard_unit_count: 577,
            verdict_counts: { disclosed: 35, partially_disclosed: 187, unknown: 277 },
            risk_counts: { high: 12, medium: 60, low: 427 },
            review_priority_counts: { high: 12, medium: 60, low: 427 },
            high_risk_total: 12,
            high_risk_reviewed: 2,
            high_priority_total: 12,
            high_priority_reviewed: 2,
            high_priority_unresolved: 10,
            applicability_counts: { applicable: 156, undetermined: 343 },
            applicability_undetermined_total: 343,
            failed_requirement_count: 0,
            not_generated_requirement_count: 0,
            analysis_incomplete_count: 0,
          };
      return Promise.resolve(new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    }));

    const { container } = renderWithQuery(<ReportDashboard reportId="report-1" />);

    expect(await screen.findByText("高优先级")).toBeInTheDocument();
    expect(screen.getByText("中优先级")).toBeInTheDocument();
    expect(screen.getByText("低优先级")).toBeInTheDocument();
    expect(screen.getByText("适用性待判定")).toBeInTheDocument();
    expect(screen.getByText("高优先级复核 2/12")).toBeInTheDocument();
    expect(screen.getByText("核查范围 577 项")).toBeInTheDocument();
    expect(screen.queryByText(/\/577/)).not.toBeInTheDocument();
    expect(screen.queryByText(/499 个当前独立判断结果/)).not.toBeInTheDocument();
    expect(screen.queryByText("高风险")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "披露结论" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "复核优先级" })).toBeInTheDocument();
    expect(screen.getByText("规则分析")).toBeInTheDocument();
    expect(screen.getByText("AI 辅助")).toBeInTheDocument();
    expect(screen.getByText("人工复核")).toBeInTheDocument();
    expect(await screen.findByText("本次分析未启用 AI 辅助")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "正式输出门禁" })).toBeInTheDocument();
    expect(screen.getByText("高优先级未解决 10 项")).toBeInTheDocument();
    expect(screen.getByText("高优先级复核完成不代表全部 577 项均已人工确认。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看整改任务" })).toHaveAttribute("href", "/reports/report-1/actions");
    expect(screen.getByRole("link", { name: "查看输出与版本" })).toHaveAttribute("href", "/reports/report-1/exports");
    const heroArtwork = container.querySelector('img[src*="module-policy-disclosure"]');
    expect(heroArtwork).toHaveClass("opacity-[0.23]");
    expect(heroArtwork?.nextElementSibling).toHaveClass(
      "bg-[linear-gradient(90deg,rgba(255,255,255,0.82)_0%,rgba(236,253,245,0.52)_52%,rgba(209,250,229,0.27)_100%)]",
    );
  });

  it("separately explains failed requirements inside the high-priority total", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      report_id: "report-1",
      run_id: "run-1",
      standard_unit_count: 577,
      verdict_counts: { unknown: 2 },
      risk_counts: { high: 1, low: 1 },
      review_priority_counts: { high: 2, low: 1 },
      high_risk_total: 2,
      high_risk_reviewed: 1,
      high_priority_total: 2,
      high_priority_reviewed: 1,
      high_priority_unresolved: 1,
      applicability_counts: { undetermined: 1, applicable: 1 },
      applicability_undetermined_total: 1,
      failed_requirement_count: 0,
      not_generated_requirement_count: 1,
      analysis_incomplete_count: 1,
    }), { status: 200, headers: { "content-type": "application/json" } })));

    renderWithQuery(<ReportDashboard reportId="report-1" />);

    expect(await screen.findByText("高优先级复核 1/2")).toBeInTheDocument();
    expect(screen.getByText("失败 0，未生成 1")).toBeInTheDocument();
    expect(screen.getByText("其中 1 条分析失败或未生成结果，需重跑后才能正式输出。")).toBeInTheDocument();
  });
});
