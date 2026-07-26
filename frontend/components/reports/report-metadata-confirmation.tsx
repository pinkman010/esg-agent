"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Play } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { analyzeReport, ApiError, confirmReportMetadata, getReport } from "@/lib/api";
import type { ReportResponse } from "@/lib/types";

function detectedValue(report: ReportResponse | undefined, key: string): string {
  const value = report?.metadata_detected?.[key as keyof typeof report.metadata_detected];
  return value === null || value === undefined ? "" : String(value);
}

function activeRunId(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 409 || typeof error.body !== "object" || error.body === null) {
    return null;
  }
  const detail = "detail" in error.body ? error.body.detail : null;
  if (typeof detail !== "object" || detail === null) return null;
  const code = "code" in detail ? detail.code : null;
  const runId = "run_id" in detail ? detail.run_id : null;
  return code === "analysis_already_running" && typeof runId === "string" && runId ? runId : null;
}

export function ReportMetadataConfirmation({ reportId }: { reportId: string }) {
  const router = useRouter();
  const reportQuery = useQuery({ queryKey: ["report", reportId], queryFn: () => getReport(reportId) });
  const [companyName, setCompanyName] = useState("");
  const [reportYear, setReportYear] = useState("");
  const [language, setLanguage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [aiAssistanceEnabled, setAIAssistanceEnabled] = useState(false);

  useEffect(() => {
    if (!reportQuery.data) return;
    setCompanyName(reportQuery.data.company_name || detectedValue(reportQuery.data, "company_name"));
    setReportYear(String(reportQuery.data.report_year ?? detectedValue(reportQuery.data, "report_year")));
    setLanguage(reportQuery.data.language || detectedValue(reportQuery.data, "language") || "zh-CN");
    setConfirmed(reportQuery.data.status === "ready_for_analysis");
  }, [reportQuery.data]);

  const confirmMutation = useMutation({
    mutationFn: () => confirmReportMetadata(reportId, {
      company_name: companyName.trim(),
      report_year: Number(reportYear),
      language,
    }),
    onSuccess: () => setConfirmed(true),
  });
  const analyzeMutation = useMutation({
    mutationFn: () => analyzeReport(reportId, aiAssistanceEnabled),
    onSuccess: (run) => router.push(`/reports/${reportId}/progress?runId=${run.run_id}`),
  });

  if (reportQuery.isLoading) return <p className="p-6 text-sm text-muted-foreground">正在读取报告信息...</p>;
  if (!reportQuery.data) return <p role="alert" className="p-6 text-sm text-red-700">报告信息读取失败。</p>;

  const editableStatuses = new Set(["uploaded", "metadata_detected", "awaiting_confirmation", "ready_for_analysis"]);
  const resultStatuses = new Set(["analysis_completed", "partially_completed", "high_risk_review_completed", "formally_exported", "reopened"]);
  const canEdit = editableStatuses.has(reportQuery.data.status);
  const hasResults = resultStatuses.has(reportQuery.data.status);
  const isAnalyzing = reportQuery.data.status === "analyzing";
  const concurrentRunId = activeRunId(analyzeMutation.error);

  return (
    <section className="mx-auto w-full max-w-4xl px-5 py-6 lg:px-7">
      <div className="border-b border-border pb-5">
        <p className="text-sm font-semibold text-emerald-700">分析准备</p>
        <h1 className="mt-1 text-2xl font-semibold">确认报告信息</h1>
        <p className="mt-1 text-sm text-muted-foreground">{reportQuery.data.original_filename} · {reportQuery.data.page_count ?? "?"} 页</p>
        <p className="mt-2 text-xs text-muted-foreground">自动识别结果仅用于预填，请在启动分析前完成人工确认。</p>
      </div>
      {hasResults && (
        <div className="mt-5 flex flex-wrap items-center gap-3 rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <span className="font-medium">该报告已有分析结果</span>
          <Link className="rounded-md bg-accent px-3 py-1.5 font-medium text-accent-foreground" href={`/reports/${reportId}/dashboard`}>查看分析结果</Link>
          <Link className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 font-medium" href={`/reports/${reportId}/review`}>进入高优先级复核</Link>
        </div>
      )}
      {isAnalyzing && (
        <div className="mt-5 rounded-md border border-blue-200 bg-blue-50 p-4 text-sm font-medium text-blue-900">分析正在进行</div>
      )}
      <div className="my-5 grid gap-5 rounded-xl border border-border bg-white p-5 shadow-sm sm:grid-cols-2">
        <label className="space-y-2 text-sm font-medium sm:col-span-2">
          <span>企业名称</span>
          <input aria-label="企业名称" className="h-10 w-full rounded-md border border-border px-3 font-normal disabled:bg-muted" disabled={!canEdit} value={companyName} onChange={(event) => setCompanyName(event.target.value)} />
        </label>
        <label className="space-y-2 text-sm font-medium">
          <span>报告年度</span>
          <input aria-label="报告年度" className="h-10 w-full rounded-md border border-border px-3 font-normal disabled:bg-muted" disabled={!canEdit} min="1900" max="2100" type="number" value={reportYear} onChange={(event) => setReportYear(event.target.value)} />
        </label>
        <label className="space-y-2 text-sm font-medium">
          <span>主要语言</span>
          <select aria-label="主要语言" className="h-10 w-full rounded-md border border-border bg-white px-3 font-normal disabled:bg-muted" disabled={!canEdit} value={language} onChange={(event) => setLanguage(event.target.value)}>
            <option value="zh-CN">中文</option>
            <option value="en">英文</option>
            <option value="zh-CN,en">中英双语</option>
          </select>
        </label>
      </div>
      {canEdit && (
        <label className="mb-5 flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50/60 p-4 text-sm">
          <input
            aria-label="启用 AI 辅助分析"
            checked={aiAssistanceEnabled}
            className="mt-1 h-4 w-4 accent-emerald-700"
            type="checkbox"
            onChange={(event) => setAIAssistanceEnabled(event.target.checked)}
          />
          <span>
            <span className="block font-medium">启用 AI 辅助分析</span>
            <span className="mt-1 block leading-5 text-muted-foreground">
              仅发送当前 requirement、有限证据片段、证据 ID、PDF 页码和必要报告信息。AI 建议不会覆盖规则结论或人工复核结果。
            </span>
          </span>
        </label>
      )}
      {canEdit && <div className="flex flex-wrap items-center gap-3 border-t border-border pt-5">
        <button
          type="button"
          className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground disabled:opacity-50"
          disabled={!companyName.trim() || !reportYear || confirmMutation.isPending}
          onClick={() => confirmMutation.mutate()}
        >
          <Check aria-hidden="true" className="h-4 w-4" />
          确认报告信息
        </button>
        {confirmed && <span className="text-sm text-emerald-700">报告信息已确认</span>}
        <button
          type="button"
          className="ml-auto inline-flex h-10 items-center gap-2 rounded-md border border-border bg-white px-4 text-sm font-medium disabled:opacity-50"
          disabled={!confirmed || analyzeMutation.isPending}
          onClick={() => analyzeMutation.mutate()}
        >
          <Play aria-hidden="true" className="h-4 w-4" />
          启动分析
        </button>
        {concurrentRunId && (
          <div className="flex w-full flex-wrap items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
            <span className="font-medium">该报告正在分析</span>
            <Link
              className="rounded-md bg-white px-3 py-1.5 font-medium"
              href={`/reports/${reportId}/progress?runId=${encodeURIComponent(concurrentRunId)}`}
            >
              查看分析进度
            </Link>
          </div>
        )}
        {analyzeMutation.isError && !concurrentRunId && (
          <span role="alert" className="w-full text-sm text-red-700">分析启动失败，请检查服务配置后重试。</span>
        )}
      </div>}
    </section>
  );
}
