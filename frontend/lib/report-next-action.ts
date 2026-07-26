import type { AnalysisRun, ReportResponse } from "./types";

type ReportLifecycle = Pick<ReportResponse, "report_id" | "status">;
type RunLifecycle = Pick<AnalysisRun, "run_id" | "report_id" | "status" | "started_at">;

export type ReportNextAction = {
  label: string;
  href: string;
  description: string;
};

export function latestActiveRunId(runs: RunLifecycle[], reportId: string): string | null {
  const activeStatuses = new Set(["pending", "running"]);
  return runs
    .filter((run) => run.report_id === reportId && activeStatuses.has(run.status))
    .sort((left, right) => {
      const leftTime = Date.parse(left.started_at ?? "") || 0;
      const rightTime = Date.parse(right.started_at ?? "") || 0;
      return rightTime - leftTime || right.run_id.localeCompare(left.run_id);
    })[0]?.run_id ?? null;
}

export function nextActionForReport(
  report: ReportLifecycle | null,
  activeRunId: string | null = null,
): ReportNextAction {
  if (!report) {
    return {
      label: "上传第一份报告",
      href: "/reports",
      description: "上传 PDF 并确认企业、年度和语言。",
    };
  }

  const reportBase = `/reports/${encodeURIComponent(report.report_id)}`;
  if (["uploaded", "metadata_detected", "awaiting_confirmation"].includes(report.status)) {
    return {
      label: "确认报告信息",
      href: `${reportBase}/confirm`,
      description: "核对自动识别的企业、年度和语言。",
    };
  }
  if (report.status === "ready_for_analysis") {
    return {
      label: "启动分析",
      href: `${reportBase}/confirm`,
      description: "确认 AI 辅助范围后启动八阶段分析。",
    };
  }
  if (report.status === "analyzing") {
    return {
      label: "查看分析进度",
      href: activeRunId
        ? `${reportBase}/progress?runId=${encodeURIComponent(activeRunId)}`
        : `${reportBase}/confirm`,
      description: "查看当前阶段、真实进度和异常状态。",
    };
  }
  if (report.status === "high_risk_review_completed") {
    return {
      label: "查看整改任务",
      href: `${reportBase}/actions`,
      description: "高优先级队列已处理，继续跟踪披露缺口。",
    };
  }
  if (report.status === "formally_exported") {
    return {
      label: "查看输出版本",
      href: `${reportBase}/exports`,
      description: "查看草稿、正式版本和对应复核范围。",
    };
  }
  if (report.status === "archived") {
    return {
      label: "查看报告记录",
      href: `${reportBase}/confirm`,
      description: "该报告已归档，可查看保留的信息。",
    };
  }
  if (report.status === "analysis_failed") {
    return {
      label: "查看失败状态",
      href: `${reportBase}/confirm`,
      description: "查看报告状态并决定是否重新上传分析。",
    };
  }
  return {
    label: "查看报告总览",
    href: `${reportBase}/dashboard`,
    description: "查看 577 项核查范围、复核优先级和适用性。",
  };
}
