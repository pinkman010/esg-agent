import { describe, expect, it } from "vitest";

import { latestActiveRunId, nextActionForReport } from "./report-next-action";

describe("nextActionForReport", () => {
  it("routes each report lifecycle state to the next real product action", () => {
    expect(nextActionForReport(null)).toEqual({
      label: "上传第一份报告",
      href: "/reports",
      description: "上传 PDF 并确认企业、年度和语言。",
    });
    expect(nextActionForReport({ report_id: "r-1", status: "awaiting_confirmation" })).toMatchObject({
      label: "确认报告信息",
      href: "/reports/r-1/confirm",
    });
    expect(nextActionForReport({ report_id: "r-1", status: "ready_for_analysis" })).toMatchObject({
      label: "启动分析",
      href: "/reports/r-1/confirm",
    });
    expect(nextActionForReport({ report_id: "r-1", status: "analyzing" }, "run-1")).toMatchObject({
      label: "查看分析进度",
      href: "/reports/r-1/progress?runId=run-1",
    });
    expect(nextActionForReport({ report_id: "r-1", status: "analysis_completed" })).toMatchObject({
      label: "查看报告总览",
      href: "/reports/r-1/dashboard",
    });
    expect(nextActionForReport({ report_id: "r-1", status: "high_risk_review_completed" })).toMatchObject({
      label: "查看整改任务",
      href: "/reports/r-1/actions",
    });
    expect(nextActionForReport({ report_id: "r-1", status: "formally_exported" })).toMatchObject({
      label: "查看输出版本",
      href: "/reports/r-1/exports",
    });
  });

  it("finds the newest active run for the current report", () => {
    expect(latestActiveRunId([
      { run_id: "run-old", report_id: "r-1", status: "completed", started_at: "2026-07-01T00:00:00Z" },
      { run_id: "run-other", report_id: "r-2", status: "running", started_at: "2026-07-03T00:00:00Z" },
      { run_id: "run-new", report_id: "r-1", status: "running", started_at: "2026-07-04T00:00:00Z" },
      { run_id: "run-pending", report_id: "r-1", status: "pending", started_at: "2026-07-02T00:00:00Z" },
    ], "r-1")).toBe("run-new");
  });
});
