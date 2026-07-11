"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { apiUrl } from "@/lib/api";

export function PdfEvidenceViewer({ reportId, initialPage = 1 }: { reportId: string; initialPage?: number }) {
  const [page, setPage] = useState(initialPage);
  useEffect(() => setPage(initialPage), [initialPage]);

  return (
    <div className="flex h-full min-h-[520px] flex-col bg-neutral-100">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-white px-3">
        <span className="text-sm font-medium">PDF 第 {page} 页</span>
        <div className="flex gap-1">
          <button aria-label="上一页" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft aria-hidden="true" className="h-4 w-4" /></button>
          <button aria-label="下一页" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" onClick={() => setPage((value) => value + 1)}><ChevronRight aria-hidden="true" className="h-4 w-4" /></button>
        </div>
      </div>
      <iframe title="PDF 证据" className="min-h-0 flex-1" src={`${apiUrl(`/api/reports/${reportId}/file`)}#page=${page}&view=FitH`} />
    </div>
  );
}
