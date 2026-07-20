import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportDashboard } from "./report-dashboard";

describe("ReportDashboard", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("separates review priority and applicability counts", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      report_id: "report-1",
      run_id: "run-1",
      verdict_counts: { disclosed: 35, partially_disclosed: 187, unknown: 355 },
      risk_counts: { high: 12, medium: 60, low: 505 },
      review_priority_counts: { high: 12, medium: 60, low: 505 },
      high_risk_total: 12,
      high_risk_reviewed: 2,
      high_priority_total: 12,
      high_priority_reviewed: 2,
      high_priority_unresolved: 10,
      applicability_counts: { applicable: 234, undetermined: 343 },
      applicability_undetermined_total: 343,
      failed_requirement_count: 0,
    }), { status: 200, headers: { "content-type": "application/json" } })));

    renderWithQuery(<ReportDashboard reportId="report-1" />);

    expect(await screen.findByText("高优先级")).toBeInTheDocument();
    expect(screen.getByText("中优先级")).toBeInTheDocument();
    expect(screen.getByText("低优先级")).toBeInTheDocument();
    expect(screen.getByText("适用性待判定")).toBeInTheDocument();
    expect(screen.getByText("高优先级复核 2/12")).toBeInTheDocument();
    expect(screen.queryByText("高风险")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看整改任务" })).toHaveAttribute("href", "/reports/report-1/actions");
    expect(screen.getByRole("link", { name: "查看输出与版本" })).toHaveAttribute("href", "/reports/report-1/exports");
  });

  it("separately explains failed requirements inside the high-priority total", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      report_id: "report-1",
      run_id: "run-1",
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
      failed_requirement_count: 1,
    }), { status: 200, headers: { "content-type": "application/json" } })));

    renderWithQuery(<ReportDashboard reportId="report-1" />);

    expect(await screen.findByText("高优先级复核 1/2")).toBeInTheDocument();
    expect(screen.getByText("其中 1 条分析失败或未生成结果，需重跑后才能正式输出。")).toBeInTheDocument();
  });
});
