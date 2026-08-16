"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileText } from "lucide-react";
import Link from "next/link";

import { listReports, listRuns } from "@/lib/api";
import { reportStatusLabels as statusLabels } from "@/lib/business-labels";
import { latestActiveRunId } from "@/lib/report-next-action";
import type { ReportResponse } from "@/lib/types";

function reportCreatedLabel(createdAt: string | null | undefined): string {
  if (!createdAt) return "创建时间待记录";
  const createdDate = new Date(createdAt);
  if (Number.isNaN(createdDate.getTime())) return "创建时间待记录";
  return `创建于 ${createdDate.toLocaleString("zh-CN", { hour12: false })}`;
}

function shortReportId(reportId: string): string {
  const idBody = reportId.replace(/^report-/, "");
  return idBody.length > 8 ? idBody.slice(0, 8) : reportId;
}

function reportDestination(report: ReportResponse, activeRunId: string | null): { href: string; label: string } {
  const base = `/reports/${encodeURIComponent(report.report_id)}`;
  if (["uploaded", "metadata_detected", "awaiting_confirmation", "ready_for_analysis", "analysis_failed", "archived"].includes(report.status)) {
    return { href: `${base}/confirm`, label: statusLabels[report.status] ?? report.status };
  }
  if (report.status === "analyzing") {
    return activeRunId
      ? { href: `${base}/progress?runId=${encodeURIComponent(activeRunId)}`, label: "查看分析进度" }
      : { href: `${base}/confirm`, label: "分析中" };
  }
  return { href: `${base}/dashboard`, label: statusLabels[report.status] ?? "查看报告总览" };
}

export function ReportList() {
  const query = useQuery({ queryKey: ["reports"], queryFn: () => listReports() });
  const hasAnalyzingReport = query.data?.items.some((report) => report.status === "analyzing") ?? false;
  const runsQuery = useQuery({
    queryKey: ["runs", "active-report-list"],
    queryFn: listRuns,
    enabled: hasAnalyzingReport,
  });

  if (query.isLoading) return <p className="py-8 text-sm text-muted-foreground">正在加载报告...</p>;
  if (query.isError) return <p role="alert" className="py-8 text-sm text-red-700">报告列表加载失败。</p>;
  if (!query.data?.items.length) {
    return (
      <div className="flex min-h-48 flex-col items-center justify-center border-y border-border py-10 text-center">
        <FileText aria-hidden="true" className="h-7 w-7 text-muted-foreground" />
        <h2 className="mt-3 text-base font-semibold">尚未上传 ESG 报告</h2>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">上传第一份 PDF，确认报告信息后即可启动 GRI 核查。</p>
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      {query.data.items.map((report) => {
        const destination = reportDestination(
          report,
          latestActiveRunId(runsQuery.data ?? [], report.report_id),
        );
        return (
          <article key={report.report_id} className="grid gap-3 rounded-xl border border-border bg-white p-4 shadow-sm sm:grid-cols-[1fr_auto_auto] sm:items-center">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{report.company_name || report.original_filename}</p>
              <p className="mt-1 truncate text-xs text-muted-foreground">{report.original_filename}</p>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span>{reportCreatedLabel(report.created_at)}</span>
                <span>{report.language || "语言待确认"}</span>
                <span>{report.page_count ? `${report.page_count} 页` : "页数待确认"}</span>
                <span className="font-mono" title={report.report_id}>ID {shortReportId(report.report_id)}</span>
              </div>
            </div>
            <div className="text-sm text-muted-foreground">{report.report_year ? `${report.report_year} 年` : "年度待确认"}</div>
            <Link
              href={destination.href}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-white px-3 text-sm font-medium hover:border-emerald-300 hover:text-emerald-800"
            >
              {destination.label}
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
          </article>
        );
      })}
    </div>
  );
}
