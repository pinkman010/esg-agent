"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getAssessmentDetail } from "@/lib/api";
import { PdfEvidenceViewer } from "@/components/evidence/pdf-evidence-viewer";
import { AssessmentDetail } from "./assessment-detail";
import { RiskQueue } from "./risk-queue";

export function ReviewWorkspace({ reportId, reviewerName }: { reportId: string; reviewerName: string }) {
  const [assessmentId, setAssessmentId] = useState<string | null>(null);
  const [pdfPage, setPdfPage] = useState(1);
  const detail = useQuery({ queryKey: ["assessment-detail", reportId, assessmentId], queryFn: () => getAssessmentDetail(reportId, assessmentId ?? ""), enabled: assessmentId !== null });

  return (
    <div className="grid min-h-[calc(100vh-3.5rem)] grid-cols-1 lg:grid-cols-[300px_minmax(360px,1fr)_minmax(360px,1fr)]">
      <aside className="border-r border-border bg-white"><div className="border-b border-border px-4 py-3"><h1 className="text-sm font-semibold">高风险复核队列</h1></div><RiskQueue reportId={reportId} onSelect={setAssessmentId} /></aside>
      <section className="min-w-0 border-r border-border bg-white">{detail.data ? <AssessmentDetail detail={detail.data} reviewerName={reviewerName} onEvidencePage={setPdfPage} /> : <p className="p-6 text-sm text-muted-foreground">从左侧选择一个 requirement 开始复核。</p>}</section>
      <section className="min-w-0"><PdfEvidenceViewer reportId={reportId} initialPage={detail.data?.evidence_items[0]?.source_pdf_page ?? pdfPage} /></section>
    </div>
  );
}
