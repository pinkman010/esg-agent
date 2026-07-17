"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, Circle, LoaderCircle, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { getReport, getRun, getRunStages, retryFailedRun } from "@/lib/api";
import { analysisStages, calculateAnalysisProgress, isAnalysisProgressStalled } from "./progress-model";

const terminalStatuses = new Set(["completed", "partially_completed", "failed"]);
const stageStatusLabels: Record<string, string> = {
  pending: "等待中",
  running: "进行中",
  completed: "已完成",
  partially_failed: "部分失败",
  failed: "失败",
};

export function AnalysisProgress({ reportId, runId }: { reportId: string; runId: string }) {
  const router = useRouter();
  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId),
    refetchInterval: (query) => terminalStatuses.has(query.state.data?.status ?? "") ? false : 1500,
  });
  const run = runQuery.data;
  const stagesQuery = useQuery({
    queryKey: ["run-stages", runId],
    queryFn: () => getRunStages(runId),
    refetchInterval: terminalStatuses.has(run?.status ?? "") ? false : 1500,
  });
  const terminalRefreshRunId = useRef<string | null>(null);
  const stagesFetched = stagesQuery.isFetched;
  const refetchStages = stagesQuery.refetch;
  useEffect(() => {
    if (!run || !terminalStatuses.has(run.status) || !stagesFetched || terminalRefreshRunId.current === runId) return;
    terminalRefreshRunId.current = runId;
    void refetchStages();
  }, [refetchStages, run, runId, stagesFetched]);
  const reportQuery = useQuery({ queryKey: ["report", reportId], queryFn: () => getReport(reportId) });
  const retryMutation = useMutation({
    mutationFn: () => retryFailedRun(runId, "重跑失败 requirement"),
    onSuccess: (newRun) => router.push(`/reports/${reportId}/progress?runId=${newRun.run_id}`),
  });
  const byCode = new Map((stagesQuery.data ?? []).map((stage) => [stage.stage_code, stage]));
  const progress = calculateAnalysisProgress(run?.status, stagesQuery.data ?? []);
  const isStalled = isAnalysisProgressStalled(run?.status, stagesQuery.data ?? []);
  const currentStageLabel = analysisStages.find(([code]) => code === progress.currentStageCode)?.[1] ?? null;
  const report = reportQuery.data;
  const reportTitle = report?.company_name
    ? `${report.company_name}${report.report_year ? ` · ${report.report_year} 年` : ""}`
    : report?.original_filename ?? "ESG 报告";
  const resultAvailable = run?.status === "completed" || run?.status === "partially_completed";

  const statusMessage = !run
    ? "正在读取进度..."
    : run.status === "completed"
      ? "分析完成"
      : run.status === "partially_completed"
        ? "分析已完成，部分项目需要重跑"
        : run.status === "failed"
          ? "分析未完成，请查看失败阶段"
          : run.status === "pending"
            ? "等待分析"
            : `分析进度 ${progress.percent}%`;

  if (runQuery.isError || stagesQuery.isError || reportQuery.isError) {
    return <p className="p-6 text-sm text-red-700">分析进度读取失败，请稍后重试。</p>;
  }

  return (
    <section className="mx-auto w-full max-w-4xl px-6 py-6">
      <div className="border-b border-border pb-5">
        <p className="text-sm font-medium">{reportTitle}</p>
        {report?.company_name && <p className="mt-1 text-xs text-muted-foreground">{report.original_filename}</p>}
        <h1 className="mt-1 text-xl font-semibold">GRI 核查进度</h1>
        <p className="mt-2 text-sm text-muted-foreground">分析在后台继续运行，可以离开此页面后再返回。</p>
      </div>
      <div className="py-6">
        <p className="text-sm font-semibold">{statusMessage}</p>
        {run?.status === "running" && currentStageLabel && (
          <p className="mt-1 text-sm text-muted-foreground">当前阶段：{currentStageLabel}</p>
        )}
        {isStalled && (
          <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">分析进度长时间没有更新，后台任务可能已中断。请返回报告列表查看状态。</p>
        )}
        {!terminalStatuses.has(run?.status ?? "") && run && (
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted" aria-label={`分析进度 ${progress.percent}%`}>
            <div className="h-full bg-accent" style={{ width: `${progress.percent}%` }} />
          </div>
        )}
        <div className="mt-5 divide-y divide-border border-y border-border">
          {analysisStages.map(([code, label]) => {
            const stage = byCode.get(code);
            const status = stage?.status ?? "pending";
            const Icon = status === "completed" ? Check : status === "failed" || status === "partially_failed" ? AlertTriangle : status === "running" ? LoaderCircle : Circle;
            return (
              <div key={code} className="grid grid-cols-[24px_1fr_auto] items-center gap-3 py-3">
                <Icon aria-hidden="true" className={`h-4 w-4 ${status === "running" ? "animate-spin text-accent" : status.includes("failed") ? "text-amber-600" : "text-muted-foreground"}`} />
                <span className="text-sm font-medium">{label}</span>
                <span className="text-xs text-muted-foreground">{stageStatusLabels[status] ?? "等待中"}</span>
              </div>
            );
          })}
        </div>
      </div>
      {run?.status === "partially_completed" && run.failed_requirement_count > 0 && (
        <button
          type="button"
          className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-white px-4 text-sm font-medium"
          onClick={() => retryMutation.mutate()}
        >
          <RotateCcw aria-hidden="true" className="h-4 w-4" />
          重跑 {run.failed_requirement_count} 条失败项
        </button>
      )}
      {resultAvailable && (
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href={`/reports/${reportId}/dashboard`}
            className="inline-flex h-10 items-center rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground"
          >
            查看分析结果
          </Link>
          <Link
            href={`/reports/${reportId}/review`}
            className="inline-flex h-10 items-center rounded-md border border-border bg-white px-4 text-sm font-medium"
          >
            进入高风险复核
          </Link>
        </div>
      )}
    </section>
  );
}
