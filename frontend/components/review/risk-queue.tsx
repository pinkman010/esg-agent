"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ChevronRight, CircleHelp } from "lucide-react";
import { useEffect, useState } from "react";

import { getApplicabilityQueue, getReviewQueue, saveApplicabilityBatch } from "@/lib/api";
import { PaginationControls } from "@/components/ui/pagination-controls";

const PAGE_SIZE = 50;

const reasonLabels: Record<string, string> = {
  unknown_verdict: "系统无法确认披露情况",
  no_valid_evidence: "未找到有效证据",
  evidence_quality_risk: "证据质量需要人工确认",
  non_substantive_evidence_only: "当前仅有索引或从略说明",
  risk_not_calculated: "风险尚未完成计算",
  sufficiency_conflict: "披露结论与证据充分性冲突",
  severe_evidence_quality: "证据存在严重质量异常",
  evidence_invalidated: "证据已被人工判定无效",
  page_conflict: "证据页码存在冲突",
  source_conflict: "证据来源存在冲突",
  analysis_failed: "该要求分析失败",
};

export function RiskQueue({ reportId, onSelect, queueType = "priority", reviewerName }: { reportId: string; onSelect?: (assessmentId: string) => void; queueType?: "priority" | "applicability"; reviewerName?: string }) {
  const [page, setPage] = useState(1);
  const [batchNote, setBatchNote] = useState("");
  const [batchMessage, setBatchMessage] = useState("");
  const queryClient = useQueryClient();
  useEffect(() => setPage(1), [reportId, queueType]);
  const query = useQuery({
    queryKey: [queueType === "priority" ? "review-queue" : "applicability-queue", reportId, page, PAGE_SIZE],
    queryFn: () => queueType === "priority" ? getReviewQueue(reportId, page, PAGE_SIZE) : getApplicabilityQueue(reportId, page, PAGE_SIZE),
  });
  const batchMutation = useMutation({
    mutationFn: (status: "applicable" | "not_applicable_confirmed") => saveApplicabilityBatch(reportId, {
      assessment_ids: query.data?.items.map((item) => item.assessment_id) ?? [],
      reviewed_applicability_status: status,
      reviewer_name: reviewerName ?? "",
      reviewer_note: batchNote,
    }),
    onMutate: () => setBatchMessage(""),
    onSuccess: async (result) => {
      setBatchNote("");
      setBatchMessage(`已批量处理 ${result.updated_count} 条适用性判断。`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["applicability-queue", reportId] }),
        queryClient.invalidateQueries({ queryKey: ["assessment-detail", reportId] }),
      ]);
    },
  });

  if (query.isLoading) return <p className="p-4 text-sm text-muted-foreground">正在加载{queueType === "priority" ? "高优先级" : "适用性待判定"}队列...</p>;
  if (!query.data?.items.length && query.data?.total === 0) return <p className="p-4 text-sm text-muted-foreground">当前没有{queueType === "priority" ? "待复核的高优先级项目" : "适用性待判定项目"}。</p>;

  return (
    <div>
      {queueType === "applicability" && query.data && (
        <div className="space-y-2 border-b border-border p-3">
          <p className="text-xs text-muted-foreground">批量处理当前页 {query.data.items.length} 条；每次判断均写入追加式审计记录。</p>
          <textarea
            className="min-h-16 w-full rounded-md border border-border px-2 py-1.5 text-xs"
            placeholder="批量复核说明（必填）"
            value={batchNote}
            onChange={(event) => setBatchNote(event.target.value)}
          />
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              className="rounded-md bg-accent px-2 py-2 text-xs font-medium text-accent-foreground disabled:opacity-50"
              disabled={!batchNote.trim() || !reviewerName || batchMutation.isPending}
              onClick={() => batchMutation.mutate("applicable")}
            >
              批量确认本页为适用
            </button>
            <button
              type="button"
              className="rounded-md border border-border bg-white px-2 py-2 text-xs font-medium disabled:opacity-50"
              disabled={!batchNote.trim() || !reviewerName || batchMutation.isPending}
              onClick={() => batchMutation.mutate("not_applicable_confirmed")}
            >
              批量确认本页不适用
            </button>
          </div>
          {batchMessage && <p className="text-xs text-emerald-700">{batchMessage}</p>}
          {batchMutation.isError && <p className="text-xs text-red-600">批量处理失败，队列可能已变化，请刷新后重试。</p>}
        </div>
      )}
      <div className="divide-y divide-border">{query.data?.items.map((item) => {
        const Icon = queueType === "priority" ? AlertTriangle : CircleHelp;
        return (
        <button
          key={item.assessment_id}
          type="button"
          className="grid w-full grid-cols-[20px_1fr_18px] gap-2 px-3 py-3 text-left hover:bg-muted"
          onClick={() => onSelect?.(item.assessment_id)}
        >
          <Icon aria-hidden="true" className={`mt-0.5 h-4 w-4 ${queueType === "priority" ? "text-red-600" : "text-amber-600"}`} />
          <span className="min-w-0">
            <span className="block text-sm font-semibold">{item.requirement_id}</span>
            <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.requirement_name_zh}</span>
            <span className={`mt-1 block text-xs ${queueType === "priority" ? "text-red-700" : "text-amber-700"}`}>{queueType === "applicability" ? "尚未确认是否适用于企业" : reasonLabels[item.risk_reason_codes.at(-1) ?? ""] ?? "需要人工复核"}</span>
          </span>
          <ChevronRight aria-hidden="true" className="mt-1 h-4 w-4 text-muted-foreground" />
        </button>
        );
      })}</div>
      {query.data && <div className="px-3"><PaginationControls page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPageChange={setPage} /></div>}
    </div>
  );
}
