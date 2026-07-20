import type {
  AIAssessmentSuggestion,
  AssessmentDetailResponse,
  AssessmentVerdict,
  ReviewSnapshotRequest,
} from "@/lib/types";

export type ReviewDraft = {
  verdict: AssessmentVerdict;
  rationale: string;
  missingItemsText: string;
  evidencePagesText: string;
  note: string;
  sourceSuggestionId: string | null;
};

const verdicts = new Set<AssessmentVerdict>([
  "disclosed",
  "partially_disclosed",
  "not_disclosed",
  "unknown",
]);

function assessmentVerdict(value: string | null | undefined): AssessmentVerdict {
  return value && verdicts.has(value as AssessmentVerdict)
    ? (value as AssessmentVerdict)
    : "unknown";
}

function normalizePages(pages: number[]): number[] {
  return [...new Set(pages)].sort((left, right) => left - right);
}

function ruleEvidencePages(detail: AssessmentDetailResponse): number[] {
  return normalizePages(detail.evidence_items.map((item) => item.source_pdf_page));
}

export function parseEvidencePages(value: string): number[] {
  if (!value.trim()) return [];
  const parts = value.split(",").map((part) => part.trim());
  if (parts.some((part) => !/^\d+$/.test(part) || Number(part) <= 0)) {
    throw new Error("证据页码必须是正整数");
  }
  return normalizePages(parts.map(Number));
}

export function draftFromDetail(detail: AssessmentDetailResponse): ReviewDraft {
  return {
    verdict: assessmentVerdict(detail.reviewed_verdict ?? detail.system_verdict),
    rationale: detail.rationale_display,
    missingItemsText: detail.missing_items_display.join("\n"),
    evidencePagesText: ruleEvidencePages(detail).join(", "),
    note: "",
    sourceSuggestionId: null,
  };
}

export function draftFromAISuggestion(
  detail: AssessmentDetailResponse,
  suggestion: AIAssessmentSuggestion,
): ReviewDraft {
  if (!suggestion.suggested_verdict || !suggestion.rationale_zh) {
    throw new Error("AI 建议内容不完整，无法载入人工表单");
  }
  return {
    verdict: assessmentVerdict(suggestion.suggested_verdict),
    rationale: suggestion.rationale_zh,
    missingItemsText: (suggestion.missing_items_zh ?? []).join("\n"),
    evidencePagesText: normalizePages(suggestion.evidence_pdf_pages ?? []).join(", "),
    note: "",
    sourceSuggestionId: suggestion.suggestion_id,
  };
}

function basePayload(
  detail: AssessmentDetailResponse,
  reviewerName: string,
  reasonCode: string,
  reviewerNote: string,
): ReviewSnapshotRequest {
  return {
    operation_type: "modify",
    reviewer_name: reviewerName,
    reason_code: reasonCode,
    reviewer_note: reviewerNote,
    reviewed_applicability_status: null,
    evidence_preview: null,
    expected_previous_snapshot_id: detail.latest_snapshot_id ?? null,
  };
}

export function buildManualModifyPayload(
  detail: AssessmentDetailResponse,
  draft: ReviewDraft,
  reviewerName: string,
): ReviewSnapshotRequest {
  const note = draft.note.trim();
  if (!note) throw new Error("请填写复核备注");
  const fromAI = Boolean(draft.sourceSuggestionId);
  return {
    ...basePayload(
      detail,
      reviewerName,
      fromAI ? "ai_suggestion_modified" : "manual_correction",
      fromAI ? `${note}；AI suggestion_id=${draft.sourceSuggestionId}` : note,
    ),
    reviewed_verdict: draft.verdict,
    rationale: draft.rationale.trim(),
    missing_items: draft.missingItemsText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
    evidence_pages: parseEvidencePages(draft.evidencePagesText),
  };
}

export function buildAcceptAIPayload(
  detail: AssessmentDetailResponse,
  suggestion: AIAssessmentSuggestion,
  reviewerName: string,
): ReviewSnapshotRequest {
  if (!suggestion.suggested_verdict || !suggestion.rationale_zh) {
    throw new Error("AI 建议内容不完整，无法采纳");
  }
  return {
    ...basePayload(
      detail,
      reviewerName,
      "ai_suggestion_accepted",
      `人工采纳 AI 建议；AI suggestion_id=${suggestion.suggestion_id}`,
    ),
    reviewed_verdict: assessmentVerdict(suggestion.suggested_verdict),
    rationale: suggestion.rationale_zh,
    missing_items: suggestion.missing_items_zh ?? [],
    evidence_pages: normalizePages(suggestion.evidence_pdf_pages ?? []),
  };
}

export function buildRejectAIPayload(
  detail: AssessmentDetailResponse,
  suggestion: AIAssessmentSuggestion,
  reviewerName: string,
): ReviewSnapshotRequest {
  return {
    ...basePayload(
      detail,
      reviewerName,
      "ai_suggestion_rejected",
      `人工拒绝 AI 建议并保留规则结论；AI suggestion_id=${suggestion.suggestion_id}`,
    ),
    reviewed_verdict: assessmentVerdict(detail.system_verdict),
    rationale: detail.rationale,
    missing_items: detail.missing_items,
    evidence_pages: ruleEvidencePages(detail),
  };
}
