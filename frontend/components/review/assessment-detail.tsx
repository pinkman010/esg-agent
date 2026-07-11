import type { AssessmentDetailResponse } from "@/lib/types";
import { verdictLabels } from "@/lib/business-labels";
import { ReviewEditor } from "./review-editor";

export function AssessmentDetail({ detail, reviewerName, onEvidencePage }: { detail: AssessmentDetailResponse; reviewerName: string; onEvidencePage: (page: number) => void }) {
  return (
    <div className="space-y-5 p-5">
      <div>
        <p className="text-xs font-medium text-red-700">高风险</p>
        <h2 className="mt-1 text-base font-semibold">{detail.requirement_id}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{detail.requirement_text}</p>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-muted-foreground">系统结论</dt><dd className="mt-1 font-medium">{verdictLabels[detail.system_verdict] ?? detail.system_verdict}</dd></div>
        <div><dt className="text-muted-foreground">当前结论</dt><dd className="mt-1 font-medium">{verdictLabels[detail.effective_verdict] ?? detail.effective_verdict}</dd></div>
      </dl>
      <section><h3 className="text-sm font-semibold">判断依据</h3><p className="mt-2 text-sm leading-6">{detail.rationale}</p></section>
      <section><h3 className="text-sm font-semibold">缺失项</h3><ul className="mt-2 space-y-1 text-sm text-muted-foreground">{detail.missing_items.map((item) => <li key={item}>{item}</li>)}</ul></section>
      <section><h3 className="text-sm font-semibold">证据</h3><div className="mt-2 space-y-2">{detail.evidence_items.map((item) => <button type="button" key={item.evidence_id} className="w-full border-l-2 border-accent py-2 pl-3 text-left text-sm" onClick={() => onEvidencePage(item.source_pdf_page)}><span className="block text-xs font-medium text-accent">{item.page_label}</span><span className="mt-1 block leading-5 text-muted-foreground">{item.evidence_preview}</span></button>)}</div></section>
      <ReviewEditor assessmentId={detail.assessment_id} reviewerName={reviewerName} />
    </div>
  );
}
