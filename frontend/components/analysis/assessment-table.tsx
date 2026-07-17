"use client";

import { useQuery } from "@tanstack/react-query";
import { listReportAssessments } from "@/lib/api";
import { reviewStatusLabels, riskLabels, verdictLabels } from "@/lib/business-labels";

export function AssessmentTable({ reportId }: { reportId: string }) {
  const query = useQuery({ queryKey: ["report-assessments", reportId], queryFn: () => listReportAssessments(reportId) });
  if (!query.data) return <p className="p-6 text-sm text-muted-foreground">正在加载完整核查表...</p>;
  return (
    <div>
      <div className="flex items-center justify-between border-b border-border pb-3"><h1 className="text-xl font-semibold">完整 GRI 核查表</h1><span className="text-sm text-muted-foreground">共 {query.data.total} 条</span></div>
      <div className="mt-4 overflow-x-auto border-y border-border">
        <table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-muted text-xs text-muted-foreground"><tr><th className="px-3 py-2">Requirement</th><th className="px-3 py-2">主题</th><th className="px-3 py-2">当前结论</th><th className="px-3 py-2">风险</th><th className="px-3 py-2">复核状态</th><th className="px-3 py-2">证据页</th></tr></thead><tbody className="divide-y divide-border">{query.data.items.map((item) => <tr key={item.assessment_id}><td className="px-3 py-3 font-medium">{item.requirement_id}</td><td className="px-3 py-3">{item.gri_topic}</td><td className="px-3 py-3">{verdictLabels[item.effective_verdict] ?? item.effective_verdict}</td><td className="px-3 py-3">{riskLabels[item.risk_level] ?? item.risk_level}</td><td className="px-3 py-3">{reviewStatusLabels[item.review_status] ?? "待确认"}</td><td className="px-3 py-3">{item.source_pdf_pages.join(", ") || "-"}</td></tr>)}</tbody></table>
      </div>
    </div>
  );
}
