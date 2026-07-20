"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileText } from "lucide-react";
import Link from "next/link";

import { listReports } from "@/lib/api";

const statusLabels: Record<string, string> = {
  uploaded: "待确认报告信息",
  metadata_detected: "待确认报告信息",
  awaiting_confirmation: "待确认报告信息",
  ready_for_analysis: "待启动分析",
  analyzing: "分析中",
  analysis_completed: "分析已完成",
  partially_completed: "部分完成",
  analysis_failed: "分析失败",
  high_risk_review_completed: "高优先级复核已完成",
  formally_exported: "已生成正式输出",
  reopened: "已重新开启",
  archived: "已归档",
};

export function ReportList() {
  const query = useQuery({ queryKey: ["reports"], queryFn: () => listReports() });

  if (query.isLoading) return <p className="py-8 text-sm text-muted-foreground">正在加载报告...</p>;
  if (query.isError) return <p className="py-8 text-sm text-red-700">报告列表加载失败。</p>;
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
    <div className="divide-y divide-border border-y border-border">
      {query.data.items.map((report) => (
        <div key={report.report_id} className="grid gap-3 py-4 sm:grid-cols-[1fr_auto_auto] sm:items-center">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{report.company_name || report.original_filename}</p>
            <p className="mt-1 truncate text-xs text-muted-foreground">{report.original_filename}</p>
          </div>
          <div className="text-sm text-muted-foreground">{report.report_year ? `${report.report_year} 年` : "年度待确认"}</div>
          <Link
            href={`/reports/${report.report_id}/confirm`}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium"
          >
            {statusLabels[report.status] ?? report.status}
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
      ))}
    </div>
  );
}
