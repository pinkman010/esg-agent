import { ActionCreator } from "@/components/actions/action-creator";
import {
  applicabilityStatusLabels,
  evidenceStatusLabels,
  reviewPriorityLabels,
  verdictLabels,
} from "@/lib/business-labels";
import type { AssessmentDetailResponse } from "@/lib/types";
import type { AIAvailability } from "./ai-suggestion-panel";
import { ReviewEditor } from "./review-editor";

type Props = {
  reportId: string;
  detail: AssessmentDetailResponse;
  aiAvailability: AIAvailability;
  reviewerName: string;
  onEvidencePage: (page: number) => void;
};

function evidenceSourceLabel(sourceMethod: string) {
  if (sourceMethod === "pdfplumber") return "PDF 原文";
  if (sourceMethod === "ocr") return "OCR 识别文本";
  return sourceMethod;
}

export function AssessmentDetail({ reportId, detail, aiAvailability, reviewerName, onEvidencePage }: Props) {
  const systemRationaleDisplay = detail.system_rationale_display ?? detail.rationale_display;
  const systemMissingItemsDisplay = detail.system_missing_items_display ?? detail.missing_items_display;
  const requirementTextDisplay = /[\u4e00-\u9fff]/.test(detail.requirement_text)
    ? detail.requirement_text
    : null;

  return (
    <div className="space-y-5 p-5">
      <header>
        <p className="text-xs font-medium text-red-700">
          {reviewPriorityLabels[detail.review_priority] ?? detail.review_priority}
        </p>
        <h2 className="mt-1 text-base font-semibold">{detail.requirement_id}</h2>
        {requirementTextDisplay && (
          <p className="mt-2 text-sm text-muted-foreground">{requirementTextDisplay}</p>
        )}
      </header>

      <section aria-labelledby="rule-analysis-heading" className="space-y-4 rounded-xl border border-border bg-slate-50/60 p-4">
        <div>
          <p className="text-xs font-medium text-muted-foreground">第 1 层 · 系统字段不可变</p>
          <h3 id="rule-analysis-heading" className="mt-1 text-sm font-semibold">规则分析</h3>
          <p className="mt-2 text-sm font-medium">
            规则结论：{verdictLabels[detail.system_verdict] ?? detail.system_verdict}
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-muted-foreground">证据状态</dt>
            <dd className="mt-1 font-medium">{evidenceStatusLabels[detail.evidence_status ?? ""] ?? "历史数据未记录"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">适用性状态</dt>
            <dd className="mt-1 font-medium">{applicabilityStatusLabels[detail.applicability_status ?? ""] ?? "历史数据未记录"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">复核优先级</dt>
            <dd className="mt-1 font-medium">{reviewPriorityLabels[detail.review_priority] ?? detail.review_priority}</dd>
          </div>
        </dl>

        <div>
          <h4 className="text-sm font-semibold">判断依据</h4>
          <p className="mt-2 text-sm leading-6">{systemRationaleDisplay}</p>
        </div>

        <div>
          <h4 className="text-sm font-semibold">缺失项</h4>
          {systemMissingItemsDisplay.length > 0 ? (
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {systemMissingItemsDisplay.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">无</p>
          )}
        </div>

        <div>
          <h4 className="text-sm font-semibold">规则证据</h4>
          {detail.evidence_items.length > 0 ? (
            <div className="mt-2 space-y-2">
              {detail.evidence_items.map((item) => {
                const isLowQualityOcr =
                  item.source_method === "ocr" &&
                  item.quality_flags.includes("needs_manual_review");

                return (
                  <div
                    key={item.evidence_id}
                    className="w-full border-l-2 border-accent py-2 pl-3 text-left text-sm"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-accent">{item.page_label}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-muted-foreground">
                        {evidenceSourceLabel(item.source_method)}
                      </span>
                    </div>
                    {isLowQualityOcr ? (
                      <div className="mt-2 space-y-2">
                        <p className="text-sm font-medium text-amber-800">
                          OCR 识别质量不足，请核对右侧 PDF 原页。
                        </p>
                        <details className="text-muted-foreground">
                          <summary className="cursor-pointer text-xs font-medium text-foreground">
                            查看原始 OCR 识别文本
                          </summary>
                          <p className="mt-2 break-words leading-5">{item.evidence_preview}</p>
                        </details>
                      </div>
                    ) : (
                      <p className="mt-1 break-words leading-5 text-muted-foreground">
                        {item.evidence_preview}
                      </p>
                    )}
                    <button
                      type="button"
                      aria-label={`核对 PDF 原页：${item.page_label}`}
                      className="mt-2 text-xs font-medium text-accent underline-offset-4 hover:underline"
                      onClick={() => onEvidencePage(item.source_pdf_page)}
                    >
                      核对 PDF 原页
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">暂无规则证据</p>
          )}
        </div>
      </section>

      <ReviewEditor
        key={`review-${detail.assessment_id}`}
        detail={detail}
        aiAvailability={aiAvailability}
        reviewerName={reviewerName}
        onEvidencePage={onEvidencePage}
      />
      <ActionCreator
        key={`action-${detail.assessment_id}`}
        reportId={reportId}
        assessmentId={detail.assessment_id}
        requirementId={detail.requirement_id}
        reviewerName={reviewerName}
        missingItems={detail.missing_items_display}
      />
    </div>
  );
}
