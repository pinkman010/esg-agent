import type { AssessmentDetailResponse } from "@/lib/types";
import { applicabilityStatusLabels, evidenceStatusLabels, reviewPriorityLabels, verdictLabels } from "@/lib/business-labels";
import { ReviewEditor } from "./review-editor";
import { ActionCreator } from "@/components/actions/action-creator";

export function AssessmentDetail({ reportId, detail, reviewerName, onEvidencePage }: { reportId: string; detail: AssessmentDetailResponse; reviewerName: string; onEvidencePage: (page: number) => void }) {
  return (
    <div className="space-y-5 p-5">
      <div>
        <p className="text-xs font-medium text-red-700">{reviewPriorityLabels[detail.review_priority] ?? detail.review_priority}</p>
        <h2 className="mt-1 text-base font-semibold">{detail.requirement_id}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{detail.requirement_text}</p>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-muted-foreground">系统结论</dt><dd className="mt-1 font-medium">{verdictLabels[detail.system_verdict] ?? detail.system_verdict}</dd></div>
        <div><dt className="text-muted-foreground">当前结论</dt><dd className="mt-1 font-medium">{verdictLabels[detail.effective_verdict] ?? detail.effective_verdict}</dd></div>
        <div><dt className="text-muted-foreground">证据状态</dt><dd className="mt-1 font-medium">{evidenceStatusLabels[detail.evidence_status ?? ""] ?? "历史数据未记录"}</dd></div>
        <div><dt className="text-muted-foreground">适用性状态</dt><dd className="mt-1 font-medium">{applicabilityStatusLabels[detail.applicability_status ?? ""] ?? "历史数据未记录"}</dd></div>
        <div><dt className="text-muted-foreground">复核优先级</dt><dd className="mt-1 font-medium">{reviewPriorityLabels[detail.review_priority] ?? detail.review_priority}</dd></div>
      </dl>
      <section><h3 className="text-sm font-semibold">判断依据</h3><p className="mt-2 text-sm leading-6">{detail.rationale_display}</p></section>
      <section><h3 className="text-sm font-semibold">缺失项</h3><ul className="mt-2 space-y-1 text-sm text-muted-foreground">{detail.missing_items_display.map((item) => <li key={item}>{item}</li>)}</ul></section>
      <section><h3 className="text-sm font-semibold">证据</h3><div className="mt-2 space-y-2">{detail.evidence_items.map((item) => <button type="button" key={item.evidence_id} className="w-full border-l-2 border-accent py-2 pl-3 text-left text-sm" onClick={() => onEvidencePage(item.source_pdf_page)}><span className="block text-xs font-medium text-accent">{item.page_label}</span><span className="mt-1 block leading-5 text-muted-foreground">{item.evidence_preview}</span></button>)}</div></section>
      <ReviewEditor key={`review-${detail.assessment_id}`} assessmentId={detail.assessment_id} reviewerName={reviewerName} />
      <ActionCreator key={`action-${detail.assessment_id}`} reportId={reportId} assessmentId={detail.assessment_id} requirementId={detail.requirement_id} reviewerName={reviewerName} missingItems={detail.missing_items_display} />
    </div>
  );
}
