"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ClipboardCheck,
  FileCheck2,
  FileOutput,
  FileText,
  Home,
  History,
  LayoutDashboard,
  ListChecks,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { getReport } from "@/lib/api";
import { reportIdFromPath } from "@/lib/report-route";

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

function navClass(active: boolean): string {
  return [
    "flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
    "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
    active
      ? "bg-emerald-50 font-semibold text-emerald-800"
      : "text-muted-foreground hover:bg-muted hover:text-foreground",
  ].join(" ");
}

export function ReportContextNav() {
  const pathname = usePathname();
  const reportId = reportIdFromPath(pathname);
  const reportQuery = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => getReport(reportId ?? ""),
    enabled: reportId !== null,
  });

  const globalItems = [
    { href: "/", label: "工作台首页", icon: Home },
    { href: "/reports", label: "ESG 报告", icon: FileText },
  ];
  const encodedReportId = reportId ? encodeURIComponent(reportId) : null;
  const reportItems = encodedReportId
    ? [
        { href: `/reports/${encodedReportId}/dashboard`, label: "报告总览", icon: LayoutDashboard },
        { href: `/reports/${encodedReportId}/assessments`, label: "完整核查", icon: ListChecks },
        { href: `/reports/${encodedReportId}/review`, label: "人工复核", icon: ClipboardCheck },
        { href: `/reports/${encodedReportId}/actions`, label: "整改任务", icon: FileCheck2 },
        { href: `/reports/${encodedReportId}/exports`, label: "输出版本", icon: FileOutput },
        { href: `/reports/${encodedReportId}/audit`, label: "审计时间线", icon: History },
      ]
    : [];

  return (
    <nav aria-label="页面导航" className="flex flex-col">
      <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">全局</p>
      <div className="space-y-1">
        {globalItems.map((item) => {
          const Icon = item.icon;
          const active = item.href === "/" ? pathname === "/" : pathname === "/reports";
          return (
            <Link
              key={item.href}
              href={item.href}
              className={navClass(active)}
              aria-current={active ? "page" : undefined}
            >
              <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </div>

      {reportId && (
        <>
          <div className="mx-1 mt-5 rounded-xl border border-emerald-100 bg-white p-3 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">当前报告</p>
            {reportQuery.isLoading && <p className="mt-2 text-xs text-muted-foreground">正在加载报告...</p>}
            {reportQuery.isError && <p className="mt-2 text-xs text-red-700">报告上下文加载失败</p>}
            {reportQuery.data && (
              <>
                <p className="mt-2 text-sm font-semibold leading-5">
                  {reportQuery.data.company_name || reportQuery.data.original_filename}
                  {reportQuery.data.report_year ? ` · ${reportQuery.data.report_year} 年` : ""}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {reportStatusLabels[reportQuery.data.status] ?? reportQuery.data.status}
                </p>
              </>
            )}
          </div>
          <p className="mt-5 px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">报告工作区</p>
          <div className="space-y-1">
            {reportItems.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={navClass(active)}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </>
      )}
    </nav>
  );
}
