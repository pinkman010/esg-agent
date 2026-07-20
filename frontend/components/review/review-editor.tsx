"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Save } from "lucide-react";
import { useState } from "react";

import { ApiError, saveReviewSnapshot } from "@/lib/api";
import { reviewStatusLabels, verdictLabels } from "@/lib/business-labels";
import type {
  ApplicabilityBatchReviewRequest,
  AssessmentDetailResponse,
  AssessmentVerdict,
  ReviewSnapshotRequest,
} from "@/lib/types";
import { AISuggestionPanel } from "./ai-suggestion-panel";
import {
  buildAcceptAIPayload,
  buildManualModifyPayload,
  buildRejectAIPayload,
  draftFromAISuggestion,
  draftFromDetail,
} from "./review-draft";

type Props = {
  detail: AssessmentDetailResponse;
  reviewerName: string;
  onEvidencePage: (page: number) => void;
};

function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return "该核查项已被其他复核操作更新，请刷新后重试。";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "复核内容不完整，请检查备注和修改字段。";
  }
  return "复核保存失败，请重试。";
}

export function ReviewEditor({ detail, reviewerName, onEvidencePage }: Props) {
  const [draft, setDraft] = useState(() => draftFromDetail(detail));
  const [saved, setSaved] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (payload: ReviewSnapshotRequest) => saveReviewSnapshot(detail.assessment_id, payload),
    onMutate: () => {
      setSaved(false);
      setErrorMessage(null);
    },
    onSuccess: async () => {
      setSaved(true);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["applicability-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["assessment-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["report-assessments"] }),
        queryClient.invalidateQueries({ queryKey: ["report-dashboard"] }),
      ]);
    },
    onError: (error) => setErrorMessage(apiErrorMessage(error)),
  });

  const submit = (buildPayload: () => ReviewSnapshotRequest) => {
    setSaved(false);
    setErrorMessage(null);
    try {
      mutation.mutate(buildPayload());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "复核内容无效，请检查后重试。");
    }
  };

  const submitApplicability = (
    applicability: ApplicabilityBatchReviewRequest["reviewed_applicability_status"],
  ) => submit(() => ({
    operation_type: "modify",
    reviewer_name: reviewerName,
    reason_code: "applicability_reviewed",
    reviewer_note: draft.note.trim(),
    reviewed_verdict: null,
    reviewed_applicability_status: applicability,
    evidence_pages: null,
    evidence_preview: null,
    rationale: null,
    missing_items: null,
    expected_previous_snapshot_id: detail.latest_snapshot_id ?? null,
  }));

  const suggestion = detail.latest_ai_suggestion;

  return (
    <div className="space-y-5 border-t border-border pt-4">
      <AISuggestionPanel
        suggestion={suggestion}
        onEvidencePage={onEvidencePage}
        busy={mutation.isPending}
        onAccept={() => suggestion && submit(() => buildAcceptAIPayload(detail, suggestion, reviewerName))}
        onEdit={() => {
          if (!suggestion) return;
          try {
            setDraft(draftFromAISuggestion(detail, suggestion));
            setSaved(false);
            setErrorMessage(null);
          } catch (error) {
            setErrorMessage(error instanceof Error ? error.message : "AI 建议无法载入。");
          }
        }}
        onReject={() => suggestion && submit(() => buildRejectAIPayload(detail, suggestion, reviewerName))}
      />

      <section aria-labelledby="human-review-heading" className="space-y-4">
        <div>
          <h3 id="human-review-heading" className="text-sm font-semibold">人工复核</h3>
          <p className="mt-2 text-sm font-medium">
            当前有效结论：{verdictLabels[detail.effective_verdict] ?? detail.effective_verdict}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            当前复核状态：{reviewStatusLabels[detail.review_status] ?? detail.review_status}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">只有人工保存的复核记录会成为当前有效结论。</p>
        </div>

        <label className="block text-sm font-medium">
          人工结论
          <select
            className="mt-2 h-10 w-full rounded-md border border-border bg-white px-3 font-normal"
            value={draft.verdict}
            onChange={(event) => setDraft({ ...draft, verdict: event.target.value as AssessmentVerdict })}
          >
            {Object.entries(verdictLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-medium">
          人工判断依据
          <textarea
            className="mt-2 min-h-24 w-full rounded-md border border-border px-3 py-2 font-normal"
            value={draft.rationale}
            onChange={(event) => setDraft({ ...draft, rationale: event.target.value })}
          />
        </label>

        <label className="block text-sm font-medium">
          缺失项（每行一项）
          <textarea
            className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 font-normal"
            value={draft.missingItemsText}
            onChange={(event) => setDraft({ ...draft, missingItemsText: event.target.value })}
          />
        </label>

        <label className="block text-sm font-medium">
          PDF 证据页
          <input
            className="mt-2 h-10 w-full rounded-md border border-border px-3 font-normal"
            value={draft.evidencePagesText}
            placeholder="例如：41, 67"
            onChange={(event) => setDraft({ ...draft, evidencePagesText: event.target.value })}
          />
        </label>

        <label className="block text-sm font-medium">
          复核备注
          <textarea
            className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 font-normal"
            value={draft.note}
            onChange={(event) => setDraft({ ...draft, note: event.target.value })}
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={mutation.isPending}
            className="inline-flex h-9 items-center gap-2 rounded-md bg-accent px-3 text-sm font-medium text-accent-foreground disabled:opacity-50"
            onClick={() => submit(() => ({
              operation_type: "approve",
              reviewer_name: reviewerName,
              reason_code: "system_result_confirmed",
              reviewer_note: draft.note.trim(),
              reviewed_verdict: null,
              reviewed_applicability_status: null,
              evidence_pages: null,
              evidence_preview: null,
              rationale: null,
              missing_items: null,
              expected_previous_snapshot_id: detail.latest_snapshot_id ?? null,
            }))}
          >
            <Check aria-hidden="true" className="h-4 w-4" />
            快速通过规则结论
          </button>
          <button
            type="button"
            disabled={!draft.note.trim() || mutation.isPending}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50"
            onClick={() => submit(() => buildManualModifyPayload(detail, draft, reviewerName))}
          >
            <Save aria-hidden="true" className="h-4 w-4" />
            保存人工修改
          </button>
          <button
            type="button"
            disabled={!draft.note.trim() || mutation.isPending}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50"
            onClick={() => submitApplicability("applicable")}
          >
            确认适用
          </button>
          <button
            type="button"
            disabled={!draft.note.trim() || mutation.isPending}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50"
            onClick={() => submitApplicability("not_applicable_confirmed")}
          >
            确认不适用
          </button>
        </div>

        {saved && <p className="text-sm text-emerald-700">复核记录已保存</p>}
        {errorMessage && <p className="text-sm text-red-600">{errorMessage}</p>}
      </section>
    </div>
  );
}
