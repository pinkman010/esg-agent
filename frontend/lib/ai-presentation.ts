import type { AIAssessmentSuggestion } from "./types";

const statusLabels: Record<AIAssessmentSuggestion["status"], string> = {
  succeeded: "AI 建议已生成",
  failed: "AI 辅助未完成",
  skipped: "AI 辅助已跳过",
};

const guardrailLabels: Record<string, string> = {
  response_schema_invalid: "AI 返回格式未通过校验，需要人工判断。",
  evidence_page_cardinality_mismatch: "AI 证据与页码数量不一致，需要人工判断。",
  duplicate_evidence_reference: "AI 重复引用了同一证据，需要人工判断。",
  evidence_reference_out_of_scope: "AI 引用了输入范围外的证据，建议已被拦截。",
  evidence_page_mismatch: "AI 证据页与输入证据不一致，需要人工判断。",
  disclosed_without_substantive_evidence: "AI 的已披露建议缺少实质证据，建议已被拦截。",
  verdict_upgrade_requires_human_review: "AI 建议不能直接升级规则结论，需要人工判断。",
  partial_without_missing_items: "AI 的部分披露建议未说明缺失项，需要人工判断。",
  call_budget_exhausted: "本次 AI 调用已达到数量上限。",
  external_model_not_confirmed: "本次分析未授权调用外部模型。",
  ai_service_unexpected_error: "AI 服务发生异常，规则结果仍然有效。",
};

export function aiStatusLabel(status: AIAssessmentSuggestion["status"]): string {
  return statusLabels[status];
}

export function aiGuardrailLabel(code: string): string {
  return guardrailLabels[code] ?? "AI 建议触发安全校验，需要人工判断。";
}

export function formatAIConfidence(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) return "未提供";
  return `${Math.round(Math.min(1, Math.max(0, confidence)) * 100)}%`;
}

export function isUsableAISuggestion(
  suggestion: AIAssessmentSuggestion | null | undefined,
): suggestion is AIAssessmentSuggestion {
  return suggestion?.status === "succeeded" && Boolean(suggestion.suggested_verdict);
}
