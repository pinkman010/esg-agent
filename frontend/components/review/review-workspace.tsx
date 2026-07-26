"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getAssessmentDetail } from "@/lib/api";
import { PdfEvidenceViewer } from "@/components/evidence/pdf-evidence-viewer";
import { AssessmentDetail } from "./assessment-detail";
import { RiskQueue } from "./risk-queue";

export function ReviewWorkspace({ reportId, reviewerName, initialAssessmentId }: { reportId: string; reviewerName: string; initialAssessmentId?: string }) {
  const [queueType, setQueueType] = useState<"priority" | "applicability">("priority");
  const [mobilePane, setMobilePane] = useState<"queue" | "detail" | "evidence">(initialAssessmentId ? "detail" : "queue");
  const [assessmentId, setAssessmentId] = useState<string | null>(initialAssessmentId || null);
  const [selectedPdfPage, setSelectedPdfPage] = useState<number | null>(null);
  const detail = useQuery({ queryKey: ["assessment-detail", reportId, assessmentId], queryFn: () => getAssessmentDetail(reportId, assessmentId ?? ""), enabled: assessmentId !== null });

  let detailContent = <p className="p-6 text-sm text-muted-foreground">从左侧选择一个 requirement 开始复核。</p>;
  if (detail.isLoading) {
    detailContent = <p className="p-6 text-sm text-muted-foreground">正在加载核查详情...</p>;
  } else if (detail.isError) {
    detailContent = <p role="alert" className="p-6 text-sm text-red-600">核查详情加载失败，请重新选择或稍后重试。</p>;
  } else if (detail.data) {
    detailContent = <AssessmentDetail reportId={reportId} detail={detail.data} reviewerName={reviewerName} onEvidencePage={setSelectedPdfPage} />;
  }

  function selectAssessment(nextAssessmentId: string) {
    setAssessmentId(nextAssessmentId);
    setSelectedPdfPage(null);
    setMobilePane("detail");
  }

  return (
    <div className="min-h-[calc(100vh-3.5rem)]">
      <nav className="sticky top-0 z-20 grid grid-cols-3 border-b border-border bg-white p-2 xl:hidden" aria-label="复核工作台栏位">
        {([["queue", "队列"], ["detail", "判断"], ["evidence", "证据"]] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={mobilePane === value}
            className={`rounded-md px-3 py-2 text-sm font-medium ${mobilePane === value ? "bg-accent text-accent-foreground" : "text-muted-foreground"}`}
            onClick={() => setMobilePane(value)}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="grid grid-cols-1 xl:grid-cols-[300px_minmax(360px,1fr)_minmax(360px,1fr)]">
        <aside className={`${mobilePane === "queue" ? "block" : "hidden"} border-r border-border bg-white xl:block`}>
          <div className="border-b border-border p-2"><div className="grid grid-cols-2 gap-1"><button type="button" className={`rounded-md px-2 py-2 text-xs font-medium ${queueType === "priority" ? "bg-accent text-accent-foreground" : "bg-muted"}`} onClick={() => setQueueType("priority")}>高优先级复核</button><button type="button" className={`rounded-md px-2 py-2 text-xs font-medium ${queueType === "applicability" ? "bg-accent text-accent-foreground" : "bg-muted"}`} onClick={() => setQueueType("applicability")}>适用性待判定</button></div></div>
          <RiskQueue reportId={reportId} queueType={queueType} reviewerName={reviewerName} selectedAssessmentId={assessmentId} onSelect={selectAssessment} />
        </aside>
        <section className={`${mobilePane === "detail" ? "block" : "hidden"} min-w-0 border-r border-border bg-white xl:block`}>{detailContent}</section>
        <section className={`${mobilePane === "evidence" ? "block" : "hidden"} min-w-0 xl:block`}>
          {detail.data ? <PdfEvidenceViewer key={`pdf-${assessmentId}`} reportId={reportId} initialPage={selectedPdfPage ?? detail.data.evidence_items[0]?.source_pdf_page ?? 1} /> : <p className="p-6 text-sm text-muted-foreground">选择核查项后显示 PDF 证据。</p>}
        </section>
      </div>
    </div>
  );
}
