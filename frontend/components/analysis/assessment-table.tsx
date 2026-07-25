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
  if (!query.data) return <p className="p-6 text-sm text-muted-foreground">正在加载完整核查表...</p>;
  return (
    <div>
      <div className="border-b border-border pb-3">
        <h1 className="text-xl font-semibold">完整 GRI 核查范围</h1>
        <p className="mt-2 text-sm text-muted-foreground">共 {query.data.total} 项</p>
      </div>
      <div className="mt-4 overflow-x-auto border-y border-border">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-muted text-xs text-muted-foreground">
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
                <tr key={item.requirement_id} className={isContext ? "bg-muted/30 text-muted-foreground" : undefined}>
                  <td className="px-3 py-3 font-medium">
                    {item.assessment_id ? (
                      <Link
                        className="text-accent underline-offset-4 hover:underline"
                        href={`/reports/${reportId}/review?assessmentId=${encodeURIComponent(item.assessment_id)}`}
                      >
                        {item.requirement_id}
                      </Link>
                    ) : item.requirement_id}
                  </td>
                  <td className="px-3 py-3">{item.gri_topic}</td>
                  <td className="px-3 py-3">
                    {isContext
                      ? "已纳入相关判断"
                      : verdictLabels[item.effective_verdict ?? ""] ?? item.effective_verdict ?? "-"}
                  </td>
                  <td className="px-3 py-3">
                    {isContext
                      ? "-"
                      : riskLabels[item.review_priority ?? ""] ?? item.review_priority ?? "-"}
                  </td>
                  <td className="px-3 py-3">
                    {isContext
                      ? "-"
                      : reviewStatusLabels[item.review_status ?? ""] ?? "待确认"}
                  </td>
                  <td className="px-3 py-3">{isContext ? "-" : item.source_pdf_pages.join(", ") || "-"}</td>
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
