"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  Circle,
  FileCheck2,
  FileOutput,
  FileText,
  ListChecks,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { MetricCard } from "@/components/ui/metric-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { getReportDashboard, listReports, listRuns } from "@/lib/api";
import { latestActiveRunId, nextActionForReport } from "@/lib/report-next-action";

const resultStatuses = new Set([
  "analysis_completed",
  "partially_completed",
  "high_risk_review_completed",
  "formally_exported",
  "reopened",
]);

const reportStatusLabels: Record<string, string> = {
  uploaded: "待确认报告信息",
  metadata_detected: "待确认报告信息",
  awaiting_confirmation: "待确认报告信息",
  ready_for_analysis: "待启动分析",
  analyzing: "分析中",
  analysis_completed: "分析已完成",
  partially_completed: "分析部分完成",
  analysis_failed: "分析失败",
  high_risk_review_completed: "高优先级复核已完成",
  formally_exported: "已生成正式输出",
  reopened: "已重新开启",
  archived: "已归档",
};

const workflow = [
  { label: "上传报告", icon: FileText },
  { label: "信息确认", icon: Check },
  { label: "自动分析", icon: Play },
  { label: "人工复核", icon: ShieldCheck },
  { label: "整改任务", icon: FileCheck2 },
  { label: "版本输出", icon: FileOutput },
];

function workflowPosition(status: string | undefined): number {
  if (!status) return 0;
  if (["uploaded", "metadata_detected", "awaiting_confirmation"].includes(status)) return 1;
  if (status === "ready_for_analysis") return 2;
  if (["analyzing", "analysis_failed"].includes(status)) return 3;
  if (["analysis_completed", "partially_completed", "reopened"].includes(status)) return 4;
  if (status === "high_risk_review_completed") return 5;
  return 6;
}

export function HomeWorkspace() {
  const reportsQuery = useQuery({
    queryKey: ["reports", 1, 1],
    queryFn: () => listReports(1, 1),
  });
  const report = reportsQuery.data?.items[0] ?? null;
  const runsQuery = useQuery({
    queryKey: ["runs", "active-report", report?.report_id],
    queryFn: listRuns,
    enabled: report?.status === "analyzing",
  });
  const activeRunId = report && runsQuery.data
    ? latestActiveRunId(runsQuery.data, report.report_id)
    : null;
  const dashboardQuery = useQuery({
    queryKey: ["report-dashboard", report?.report_id],
    queryFn: () => getReportDashboard(report?.report_id ?? ""),
    enabled: Boolean(report && resultStatuses.has(report.status)),
  });
  const nextAction = nextActionForReport(report, activeRunId);

  if (reportsQuery.isLoading) {
    return <div className="mx-auto max-w-7xl px-6 py-8 text-sm text-muted-foreground">正在加载工作台...</div>;
  }
  if (reportsQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-12">
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">
          <h1 className="text-lg font-semibold">工作台数据加载失败</h1>
          <p className="mt-2 text-sm">请确认后端服务可用后重新加载。</p>
          <button
            type="button"
            className="mt-4 inline-flex h-9 items-center gap-2 rounded-lg border border-red-300 bg-white px-3 text-sm font-medium"
            onClick={() => reportsQuery.refetch()}
          >
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
            重新加载
          </button>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8">
        <section className="rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-8 shadow-sm">
          <p className="text-sm font-semibold text-emerald-700">企业 ESG 核查工作台</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">从第一份 ESG 报告开始</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            上传 PDF，确认报告信息，完成 GRI 核查、人工复核、整改任务和版本化输出。
          </p>
          <Link
            href={nextAction.href}
            className="mt-6 inline-flex h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-accent-foreground"
          >
            {nextAction.label}
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </section>
      </div>
    );
  }

  const dashboard = dashboardQuery.data;
  const priorities = dashboard?.review_priority_counts ?? dashboard?.risk_counts ?? {};
  const currentWorkflowPosition = workflowPosition(report.status);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-6 lg:px-7">
      <section className="grid gap-6 rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-white p-6 shadow-sm lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-emerald-700">当前演示报告</p>
            <StatusBadge tone={report.status.includes("failed") ? "danger" : report.status === "analyzing" ? "info" : "success"}>
              {reportStatusLabels[report.status] ?? report.status}
            </StatusBadge>
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            {report.company_name || report.original_filename}
            {report.report_year ? ` · ${report.report_year} 年` : ""}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {report.original_filename}
            {report.page_count ? ` · ${report.page_count} 页` : ""}
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href={nextAction.href}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-accent-foreground"
            >
              {nextAction.label}
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
            <Link
              href="/reports"
              className="inline-flex h-10 items-center rounded-lg border border-border bg-white px-4 text-sm font-medium"
            >
              重新上传并演示
            </Link>
          </div>
        </div>
        {dashboard && (
          <div className="min-w-40 text-left lg:text-right">
            <p className="text-5xl font-semibold tracking-tight text-emerald-950">{dashboard.standard_unit_count}</p>
            <p className="mt-2 text-sm text-muted-foreground">项 GRI 核查范围</p>
          </div>
        )}
      </section>

      {dashboardQuery.isError && (
        <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          当前报告已存在，但汇总指标暂时无法读取。可继续通过报告入口查看状态。
        </div>
      )}

      {dashboard && (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="当前报告关键指标">
          <MetricCard label="高优先级" value={priorities.high ?? 0} description="优先进入人工复核" tone="danger" />
          <MetricCard label="中优先级" value={priorities.medium ?? 0} description="允许按需人工复核" tone="warning" />
          <MetricCard label="低优先级" value={priorities.low ?? 0} description="证据和规则状态正常" tone="success" />
          <MetricCard label="适用性待确认" value={dashboard.applicability_undetermined_total} description="需要企业条件判断" tone="info" />
        </section>
      )}

      <section className="grid gap-4 xl:grid-cols-[1.3fr_.7fr]">
        <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold">产品闭环</h2>
            <span className="text-xs text-muted-foreground">状态来自当前报告</span>
          </div>
          <ol className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            {workflow.map((item, index) => {
              const Icon = item.icon;
              const completed = index < currentWorkflowPosition;
              const current = index === currentWorkflowPosition;
              return (
                <li key={item.label} className="flex items-center gap-2 xl:flex-col xl:text-center">
                  <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${completed ? "bg-emerald-100 text-emerald-800" : current ? "bg-accent text-white" : "bg-muted text-muted-foreground"}`}>
                    {completed ? <Check aria-hidden="true" className="h-4 w-4" /> : current ? <Icon aria-hidden="true" className="h-4 w-4" /> : <Circle aria-hidden="true" className="h-4 w-4" />}
                  </span>
                  <span className="text-xs font-medium">{item.label}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-5 rounded-lg bg-muted/60 p-3 text-xs leading-5 text-muted-foreground">
            高优先级复核完成只表示该队列已处理，不代表全部 577 项均已人工确认。
          </p>
        </div>

        <div className="rounded-xl border border-border bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">建议下一步</p>
          <h2 className="mt-3 text-lg font-semibold">{nextAction.label}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{nextAction.description}</p>
          <Link
            href={nextAction.href}
            className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-accent-foreground"
          >
            继续处理
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
          {dashboard && dashboard.high_priority_total > 0 && (
            <Link
              href={`/reports/${encodeURIComponent(report.report_id)}/review`}
              className="mt-3 flex items-center gap-2 text-sm font-semibold text-emerald-700"
            >
              <ListChecks aria-hidden="true" className="h-4 w-4" />
              进入三栏复核
            </Link>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-sky-100 bg-sky-50/70 p-4 text-sm text-sky-950">
        <p className="font-semibold">规则、AI、人工分层留痕</p>
        <p className="mt-1 text-xs leading-5 text-sky-800">
          AI 输出仅供分析辅助，不替代 ESG 专业判断或最终合规结论。
        </p>
      </section>
    </div>
  );
}
