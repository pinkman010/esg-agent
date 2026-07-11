"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronRight } from "lucide-react";

import { getReviewQueue } from "@/lib/api";

const reasonLabels: Record<string, string> = {
  unknown_verdict: "系统无法确认披露情况",
  no_valid_evidence: "未找到有效证据",
  evidence_quality_risk: "证据质量需要人工确认",
  non_substantive_evidence_only: "当前仅有索引或从略说明",
  risk_not_calculated: "风险尚未完成计算",
};

export function RiskQueue({ reportId, onSelect }: { reportId: string; onSelect?: (assessmentId: string) => void }) {
  const query = useQuery({ queryKey: ["review-queue", reportId], queryFn: () => getReviewQueue(reportId) });

  if (query.isLoading) return <p className="p-4 text-sm text-muted-foreground">正在加载高风险队列...</p>;
  if (!query.data?.items.length) return <p className="p-4 text-sm text-muted-foreground">当前没有待复核的高风险项。</p>;

  return (
    <div className="divide-y divide-border">
      {query.data.items.map((item) => (
        <button
          key={item.assessment_id}
          type="button"
          className="grid w-full grid-cols-[20px_1fr_18px] gap-2 px-3 py-3 text-left hover:bg-muted"
          onClick={() => onSelect?.(item.assessment_id)}
        >
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 text-red-600" />
          <span className="min-w-0">
            <span className="block text-sm font-semibold">{item.requirement_id}</span>
            <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.requirement_name_zh}</span>
            <span className="mt-1 block text-xs text-red-700">{reasonLabels[item.risk_reason_codes.at(-1) ?? ""] ?? "需要人工复核"}</span>
          </span>
          <ChevronRight aria-hidden="true" className="mt-1 h-4 w-4 text-muted-foreground" />
        </button>
      ))}
    </div>
  );
}
