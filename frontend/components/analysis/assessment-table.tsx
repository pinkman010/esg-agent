"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { listReportScopeItems } from "@/lib/api";
import { reviewStatusLabels, riskLabels, verdictLabels } from "@/lib/business-labels";
import { PaginationControls } from "@/components/ui/pagination-controls";

const PAGE_SIZE = 50;

export function AssessmentTable({ reportId }: { reportId: string }) {
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["report-scope-items", reportId, page, PAGE_SIZE],
    queryFn: () => listReportScopeItems(reportId, page, PAGE_SIZE),
  });
  if (query.isLoading) return <p className="p-6 text-sm text-muted-foreground">正在加载完整核查表...</p>;
  if (query.isError) return <p role="alert" className="p-6 text-sm text-red-700">完整 GRI 核查范围加载失败，请稍后重试。</p>;
  if (!query.data) return null;
  if (query.data.total === 0) {
    return (
      <div className="rounded-xl border border-border bg-white p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold">完整 GRI 核查范围</h1>
        <p className="mt-3 text-sm text-muted-foreground">当前报告暂无 GRI 核查范围</p>
      </div>
    );
  }
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
        <div>
          <p className="text-sm font-semibold text-emerald-700">报告核查清单</p>
          <h1 className="mt-1 text-2xl font-semibold">完整 GRI 核查范围</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            独立判断项可进入人工复核；上下文条款已纳入相关判断，不重复生成结论。
          </p>
        </div>
        <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-800">共 {query.data.total} 项</span>
      </div>
      <div className="mt-4 overflow-x-auto rounded-xl border border-border bg-white shadow-sm">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-100 text-xs text-slate-600">
            <tr>
              <th className="px-3 py-2">Requirement</th>
              <th className="px-3 py-2">主题</th>
              <th className="px-3 py-2">当前结论</th>
              <th className="px-3 py-2">复核优先级</th>
              <th className="px-3 py-2">复核状态</th>
              <th className="px-3 py-2">证据页</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {query.data.items.map((item) => {
              const isContext = item.unit_status === "context_incorporated";
              return (
                <tr key={item.requirement_id} className={isContext ? "bg-slate-50 text-muted-foreground" : "hover:bg-emerald-50/30"}>
                  <td className="px-3 py-3.5 font-medium">
                    {item.assessment_id ? (
                      <Link
                        className="text-accent underline-offset-4 hover:underline"
                        href={`/reports/${reportId}/review?assessmentId=${encodeURIComponent(item.assessment_id)}`}
                      >
                        {item.requirement_id}
                      </Link>
                    ) : item.requirement_id}
                  </td>
                  <td className="px-3 py-3.5">{item.gri_topic}</td>
                  <td className="px-3 py-3.5">
                    {isContext
                      ? "已纳入相关判断"
                      : verdictLabels[item.effective_verdict ?? ""] ?? item.effective_verdict ?? "-"}
                  </td>
                  <td className="px-3 py-3.5">
                    {isContext
                      ? "-"
                      : riskLabels[item.review_priority ?? ""] ?? item.review_priority ?? "-"}
                  </td>
                  <td className="px-3 py-3.5">
                    {isContext
                      ? "-"
                      : reviewStatusLabels[item.review_status ?? ""] ?? "待确认"}
                  </td>
                  <td className="px-3 py-3.5">{isContext ? "-" : item.source_pdf_pages.join(", ") || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <PaginationControls
        page={query.data.page}
        pageSize={query.data.page_size}
        total={query.data.total}
        unitLabel="项"
        onPageChange={setPage}
      />
    </div>
  );
}
