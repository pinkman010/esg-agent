"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getAssessmentDetail } from "@/lib/api";
import { PdfEvidenceViewer } from "@/components/evidence/pdf-evidence-viewer";
import { AssessmentDetail } from "./assessment-detail";
import { RiskQueue } from "./risk-queue";

export function ReviewWorkspace({ reportId, reviewerName }: { reportId: string; reviewerName: string }) {
  const [assessmentId, setAssessmentId] = useState<string | null>(null);
  const [selectedPdfPage, setSelectedPdfPage] = useState<number | null>(null);
  const detail = useQuery({ queryKey: ["assessment-detail", reportId, assessmentId], queryFn: () => getAssessmentDetail(reportId, assessmentId ?? ""), enabled: assessmentId !== null });

  let detailContent = <p className="p-6 text-sm text-muted-foreground">从左侧选择一个 requirement 开始复核。</p>;
  if (detail.isLoading) {
    detailContent = <p className="p-6 text-sm text-muted-foreground">正在加载核查详情...</p>;
  } else if (detail.isError) {
    detailContent = <p className="p-6 text-sm text-red-600">核查详情加载失败，请重新选择或稍后重试。</p>;
  } else if (detail.data) {
    detailContent = <AssessmentDetail detail={detail.data} reviewerName={reviewerName} onEvidencePage={setSelectedPdfPage} />;
  }

  function selectAssessment(nextAssessmentId: string) {
    setAssessmentId(nextAssessmentId);
    setSelectedPdfPage(null);
  }

  return (
    <div className="grid min-h-[calc(100vh-3.5rem)] grid-cols-1 lg:grid-cols-[300px_minmax(360px,1fr)_minmax(360px,1fr)]">
      <aside className="border-r border-border bg-white"><div className="border-b border-border px-4 py-3"><h1 className="text-sm font-semibold">高风险复核队列</h1></div><RiskQueue reportId={reportId} onSelect={selectAssessment} /></aside>
      <section className="min-w-0 border-r border-border bg-white">{detailContent}</section>
      <section className="min-w-0">
        {detail.data ? <PdfEvidenceViewer reportId={reportId} initialPage={selectedPdfPage ?? detail.data.evidence_items[0]?.source_pdf_page ?? 1} /> : <p className="p-6 text-sm text-muted-foreground">选择核查项后显示 PDF 证据。</p>}
      </section>
    </div>
  );
}
