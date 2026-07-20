import { ActionCreator } from "@/components/actions/action-creator";
import {
  applicabilityStatusLabels,
  evidenceStatusLabels,
  reviewPriorityLabels,
  verdictLabels,
} from "@/lib/business-labels";
import type { AssessmentDetailResponse } from "@/lib/types";
import { ReviewEditor } from "./review-editor";

type Props = {
  reportId: string;
  detail: AssessmentDetailResponse;
  reviewerName: string;
  onEvidencePage: (page: number) => void;
};

export function AssessmentDetail({ reportId, detail, reviewerName, onEvidencePage }: Props) {
  const systemRationaleDisplay = detail.system_rationale_display ?? detail.rationale_display;
  const systemMissingItemsDisplay = detail.system_missing_items_display ?? detail.missing_items_display;

  return (
    <div className="space-y-5 p-5">
      <header>
        <p className="text-xs font-medium text-red-700">
          {reviewPriorityLabels[detail.review_priority] ?? detail.review_priority}
        </p>
        <h2 className="mt-1 text-base font-semibold">{detail.requirement_id}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{detail.requirement_text}</p>
      </header>

      <section aria-labelledby="rule-analysis-heading" className="space-y-4 rounded-md border border-border p-4">
        <div>
          <h3 id="rule-analysis-heading" className="text-sm font-semibold">规则分析</h3>
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
              {detail.evidence_items.map((item) => (
                <button
                  type="button"
                  key={item.evidence_id}
                  className="w-full border-l-2 border-accent py-2 pl-3 text-left text-sm"
                  onClick={() => onEvidencePage(item.source_pdf_page)}
                >
                  <span className="block text-xs font-medium text-accent">{item.page_label}</span>
                  <span className="mt-1 block leading-5 text-muted-foreground">{item.evidence_preview}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">暂无规则证据</p>
          )}
        </div>
      </section>

      <ReviewEditor
        key={`review-${detail.assessment_id}`}
        detail={detail}
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
