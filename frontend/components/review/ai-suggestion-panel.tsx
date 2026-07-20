import { Check, PencilLine, Sparkles, X } from "lucide-react";

import {
  aiGuardrailLabel,
  aiStatusLabel,
  formatAIConfidence,
  isUsableAISuggestion,
} from "@/lib/ai-presentation";
import { verdictLabels } from "@/lib/business-labels";
import type { AIAssessmentSuggestion } from "@/lib/types";

type Props = {
  suggestion: AIAssessmentSuggestion | null | undefined;
  onEvidencePage: (page: number) => void;
  onAccept: () => void;
  onEdit: () => void;
  onReject: () => void;
  busy: boolean;
};

export function AISuggestionPanel({
  suggestion,
  onEvidencePage,
  onAccept,
  onEdit,
  onReject,
  busy,
}: Props) {
  const usable = isUsableAISuggestion(suggestion);

  return (
    <section className="rounded-md border border-emerald-200 bg-emerald-50/40 p-4">
      <div className="flex items-center gap-2">
        <Sparkles aria-hidden="true" className="h-4 w-4 text-emerald-700" />
        <h3 className="text-sm font-semibold">AI 辅助建议</h3>
      </div>

      {!suggestion && (
        <p className="mt-3 text-sm text-muted-foreground">该核查项暂无 AI 建议</p>
      )}

      {suggestion && (
        <div className="mt-3 space-y-3 text-sm">
          <p className="font-medium">{aiStatusLabel(suggestion.status)}</p>

          {suggestion.status === "failed" && (
            <p className="text-amber-800">AI 辅助未完成，规则结果仍有效</p>
          )}

          {(suggestion.guardrail_codes ?? []).length > 0 && (
            <ul className="space-y-1 text-amber-800">
              {(suggestion.guardrail_codes ?? []).map((code) => (
                <li key={code}>{aiGuardrailLabel(code)}</li>
              ))}
            </ul>
          )}

          {usable && (
            <>
              <dl className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-muted-foreground">AI 建议结论</dt>
                  <dd className="mt-1 font-medium">
                    {verdictLabels[suggestion.suggested_verdict ?? ""] ?? "待人工判断"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">置信度</dt>
                  <dd className="mt-1 font-medium">{formatAIConfidence(suggestion.confidence)}</dd>
                </div>
              </dl>

              <div>
                <p className="text-muted-foreground">AI 判断依据</p>
                <p className="mt-1 leading-6">{suggestion.rationale_zh || "未提供"}</p>
              </div>

              <div>
                <p className="text-muted-foreground">AI 识别的缺失项</p>
                {(suggestion.missing_items_zh ?? []).length > 0 ? (
                  <ul className="mt-1 space-y-1">
                    {(suggestion.missing_items_zh ?? []).map((item) => <li key={item}>{item}</li>)}
                  </ul>
                ) : (
                  <p className="mt-1">无</p>
                )}
              </div>

              {(suggestion.evidence_pdf_pages ?? []).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {(suggestion.evidence_pdf_pages ?? []).map((page) => (
                    <button
                      key={page}
                      type="button"
                      className="rounded-md border border-emerald-300 bg-white px-2 py-1 text-xs font-medium text-emerald-800"
                      aria-label={`查看 AI 证据 PDF 第 ${page} 页`}
                      onClick={() => onEvidencePage(page)}
                    >
                      PDF 第 {page} 页
                    </button>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap gap-2 border-t border-emerald-200 pt-3">
                <button type="button" disabled={busy} className="inline-flex h-9 items-center gap-2 rounded-md bg-accent px-3 text-sm font-medium text-accent-foreground disabled:opacity-50" onClick={onAccept}>
                  <Check aria-hidden="true" className="h-4 w-4" />采纳 AI 建议
                </button>
                <button type="button" disabled={busy} className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50" onClick={onEdit}>
                  <PencilLine aria-hidden="true" className="h-4 w-4" />载入 AI 建议并修改
                </button>
                <button type="button" disabled={busy} className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50" onClick={onReject}>
                  <X aria-hidden="true" className="h-4 w-4" />拒绝 AI 建议并保留规则结论
                </button>
              </div>
            </>
          )}

          <p className="text-xs text-muted-foreground">
            {suggestion.provider} / {suggestion.model} · Prompt {suggestion.prompt_version}
            {suggestion.retry_count > 0 ? ` · 重试 ${suggestion.retry_count} 次` : ""}
          </p>
        </div>
      )}

      <p className="mt-3 border-t border-emerald-200 pt-3 text-xs text-muted-foreground">
        AI 建议仅供人工复核参考，不构成最终 GRI 合规结论。
      </p>
    </section>
  );
}
