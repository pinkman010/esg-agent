"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { analyzeReport, confirmReportMetadata, getReport } from "@/lib/api";
import type { ReportResponse } from "@/lib/types";

function detectedValue(report: ReportResponse | undefined, key: string): string {
  const value = report?.metadata_detected?.[key as keyof typeof report.metadata_detected];
  return value === null || value === undefined ? "" : String(value);
}

export function ReportMetadataConfirmation({ reportId }: { reportId: string }) {
  const router = useRouter();
  const reportQuery = useQuery({ queryKey: ["report", reportId], queryFn: () => getReport(reportId) });
  const [companyName, setCompanyName] = useState("");
  const [reportYear, setReportYear] = useState("");
  const [language, setLanguage] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!reportQuery.data) return;
    setCompanyName(reportQuery.data.company_name ?? "");
    setReportYear(String(reportQuery.data.report_year ?? detectedValue(reportQuery.data, "report_year")));
    setLanguage(reportQuery.data.language ?? detectedValue(reportQuery.data, "language") ?? "zh-CN");
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
    mutationFn: () => analyzeReport(reportId, false),
    onSuccess: (run) => router.push(`/reports/${reportId}/progress?runId=${run.run_id}`),
  });

  if (reportQuery.isLoading) return <p className="p-6 text-sm text-muted-foreground">正在读取报告信息...</p>;
  if (!reportQuery.data) return <p className="p-6 text-sm text-red-700">报告信息读取失败。</p>;

  return (
    <section className="mx-auto w-full max-w-3xl px-6 py-6">
      <div className="border-b border-border pb-5">
        <h1 className="text-xl font-semibold">确认报告信息</h1>
        <p className="mt-1 text-sm text-muted-foreground">{reportQuery.data.original_filename} · {reportQuery.data.page_count ?? "?"} 页</p>
      </div>
      <div className="grid gap-5 py-6 sm:grid-cols-2">
        <label className="space-y-2 text-sm font-medium sm:col-span-2">
          <span>企业名称</span>
          <input aria-label="企业名称" className="h-10 w-full rounded-md border border-border px-3 font-normal" value={companyName} onChange={(event) => setCompanyName(event.target.value)} />
        </label>
        <label className="space-y-2 text-sm font-medium">
          <span>报告年度</span>
          <input aria-label="报告年度" className="h-10 w-full rounded-md border border-border px-3 font-normal" min="1900" max="2100" type="number" value={reportYear} onChange={(event) => setReportYear(event.target.value)} />
        </label>
        <label className="space-y-2 text-sm font-medium">
          <span>主要语言</span>
          <select aria-label="主要语言" className="h-10 w-full rounded-md border border-border bg-white px-3 font-normal" value={language} onChange={(event) => setLanguage(event.target.value)}>
            <option value="zh-CN">中文</option>
            <option value="en">英文</option>
            <option value="zh-CN,en">中英双语</option>
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-border pt-5">
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
      </div>
    </section>
  );
}
