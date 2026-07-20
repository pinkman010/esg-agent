"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CircleHelp, Gauge, ListChecks } from "lucide-react";
import Link from "next/link";

import { getReportDashboard } from "@/lib/api";

export function ReportDashboard({ reportId }: { reportId: string }) {
  const query = useQuery({ queryKey: ["report-dashboard", reportId], queryFn: () => getReportDashboard(reportId) });
  if (!query.data) return <p className="p-6 text-sm text-muted-foreground">正在加载报告仪表盘...</p>;
  const data = query.data;
  const priorities = data.review_priority_counts ?? data.risk_counts;
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-5"><div><h1 className="text-xl font-semibold">报告仪表盘</h1><p className="mt-1 text-sm text-muted-foreground">高优先级复核 {data.high_priority_reviewed}/{data.high_priority_total}</p>{data.failed_requirement_count > 0 && <p className="mt-1 text-xs text-red-600">其中 {data.failed_requirement_count} 条分析失败或未生成结果，需重跑后才能正式输出。</p>}<p className="mt-1 text-xs text-muted-foreground">该进度仅覆盖高优先级项目，不代表全部 requirement 均已人工确认。</p></div><Link href={`/reports/${reportId}/review`} className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground"><ListChecks className="h-4 w-4" />进入复核工作台</Link></div>
      <div className="grid gap-3 py-6 sm:grid-cols-2 lg:grid-cols-4">
        {[{ label: "高优先级", value: priorities.high ?? 0, icon: AlertTriangle }, { label: "中优先级", value: priorities.medium ?? 0, icon: Gauge }, { label: "低优先级", value: priorities.low ?? 0, icon: ListChecks }, { label: "适用性待判定", value: data.applicability_undetermined_total, icon: CircleHelp }].map(({ label, value, icon: Icon }) => <div key={label} className="rounded-lg border border-border bg-white p-4"><Icon className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-2xl font-semibold">{value}</p><p className="mt-1 text-xs text-muted-foreground">{label}</p></div>)}
      </div>
      <div className="flex flex-wrap gap-5">
        <Link href={`/reports/${reportId}/assessments`} className="text-sm font-medium text-accent">查看完整 GRI 核查表</Link>
        <Link href={`/reports/${reportId}/actions`} className="text-sm font-medium text-accent">查看整改任务</Link>
        <Link href={`/reports/${reportId}/exports`} className="text-sm font-medium text-accent">查看输出与版本</Link>
      </div>
    </div>
  );
}
