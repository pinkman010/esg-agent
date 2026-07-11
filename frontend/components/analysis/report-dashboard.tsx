"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileCheck2, ListChecks } from "lucide-react";
import Link from "next/link";

import { getReportDashboard } from "@/lib/api";

export function ReportDashboard({ reportId }: { reportId: string }) {
  const query = useQuery({ queryKey: ["report-dashboard", reportId], queryFn: () => getReportDashboard(reportId) });
  if (!query.data) return <p className="p-6 text-sm text-muted-foreground">正在加载报告仪表盘...</p>;
  const data = query.data;
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-6">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-5"><div><h1 className="text-xl font-semibold">报告仪表盘</h1><p className="mt-1 text-sm text-muted-foreground">高风险复核 {data.high_risk_reviewed}/{data.high_risk_total}</p></div><Link href={`/reports/${reportId}/review`} className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground"><ListChecks className="h-4 w-4" />进入复核工作台</Link></div>
      <div className="grid gap-3 py-6 sm:grid-cols-2 lg:grid-cols-4">
        {[{ label: "高风险", value: data.high_risk_total, icon: AlertTriangle }, { label: "已完成高风险复核", value: data.high_risk_reviewed, icon: CheckCircle2 }, { label: "分析失败项", value: data.failed_requirement_count, icon: FileCheck2 }, { label: "已生成结果", value: Object.values(data.verdict_counts).reduce((a, b) => a + b, 0), icon: ListChecks }].map(({ label, value, icon: Icon }) => <div key={label} className="rounded-lg border border-border bg-white p-4"><Icon className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-2xl font-semibold">{value}</p><p className="mt-1 text-xs text-muted-foreground">{label}</p></div>)}
      </div>
      <Link href={`/reports/${reportId}/assessments`} className="text-sm font-medium text-accent">查看完整 GRI 核查表</Link>
    </div>
  );
}
