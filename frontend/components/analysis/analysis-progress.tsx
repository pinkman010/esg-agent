"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, Circle, LoaderCircle, RotateCcw } from "lucide-react";

import { getRun, getRunStages, retryFailedRun } from "@/lib/api";

const stages = [
  ["file_validation", "文件检查"],
  ["pdf_parsing", "PDF 解析"],
  ["report_structure", "报告结构识别"],
  ["requirement_matching", "GRI requirement 匹配"],
  ["evidence_assessment", "证据与结论生成"],
  ["risk_classification", "风险分级"],
  ["result_summary", "结果汇总"],
] as const;

const terminalStatuses = new Set(["completed", "partially_completed", "failed"]);

export function AnalysisProgress({ reportId, runId }: { reportId: string; runId: string }) {
  const runQuery = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId),
    refetchInterval: (query) => terminalStatuses.has(query.state.data?.status ?? "") ? false : 1500,
  });
  const stagesQuery = useQuery({
    queryKey: ["run-stages", runId],
    queryFn: () => getRunStages(runId),
    refetchInterval: 1500,
  });
  const retryMutation = useMutation({ mutationFn: () => retryFailedRun(runId, "重跑失败 requirement") });
  const run = runQuery.data;
  const byCode = new Map((stagesQuery.data ?? []).map((stage) => [stage.stage_code, stage]));

  return (
    <section className="mx-auto w-full max-w-4xl px-6 py-6">
      <div className="border-b border-border pb-5">
        <p className="text-xs text-muted-foreground">报告 {reportId}</p>
        <h1 className="mt-1 text-xl font-semibold">GRI 核查进度</h1>
        <p className="mt-2 text-sm text-muted-foreground">分析在后台继续运行，可以离开此页面后再返回。</p>
      </div>
      <div className="py-6">
        <p className="text-sm font-semibold">
          {run ? `${run.succeeded_requirement_count} / ${run.eligible_requirement_count} 条已生成结果` : "正在读取进度..."}
        </p>
        <div className="mt-5 divide-y divide-border border-y border-border">
          {stages.map(([code, label]) => {
            const stage = byCode.get(code);
            const status = stage?.status ?? "pending";
            const Icon = status === "completed" ? Check : status === "failed" || status === "partially_failed" ? AlertTriangle : status === "running" ? LoaderCircle : Circle;
            return (
              <div key={code} className="grid grid-cols-[24px_1fr_auto] items-center gap-3 py-3">
                <Icon aria-hidden="true" className={`h-4 w-4 ${status === "running" ? "animate-spin text-accent" : status.includes("failed") ? "text-amber-600" : "text-muted-foreground"}`} />
                <span className="text-sm font-medium">{label}</span>
                <span className="text-xs text-muted-foreground">{stage && stage.total_units ? `${stage.completed_units}/${stage.total_units}` : status}</span>
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
    </section>
  );
}
