"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiUrl } from "@/lib/api";

export function PdfEvidenceViewer({ reportId, initialPage = 1 }: { reportId: string; initialPage?: number }) {
  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    setPage(initialPage);
    setIsLoading(true);
    setLoadFailed(false);
  }, [initialPage, reportId]);

  function changePage(nextPage: number) {
    setPage(nextPage);
    setIsLoading(true);
    setLoadFailed(false);
  }

  function showLoadError() {
    setIsLoading(false);
    setLoadFailed(true);
  }

  return (
    <div className="flex h-full min-h-[520px] flex-col bg-neutral-100">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-white px-3">
        <span className="text-sm font-medium">PDF 第 {page} 页</span>
        <div className="flex gap-1">
          <button aria-label="上一页" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" disabled={page <= 1} onClick={() => changePage(Math.max(1, page - 1))}><ChevronLeft aria-hidden="true" className="h-4 w-4" /></button>
          <button aria-label="下一页" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" onClick={() => changePage(page + 1)}><ChevronRight aria-hidden="true" className="h-4 w-4" /></button>
        </div>
      </div>
      <div className="relative flex min-h-0 flex-1">
        {isLoading && !loadFailed ? <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">正在加载 PDF 证据...</p> : null}
        {loadFailed ? <p className="absolute inset-0 grid place-items-center px-6 text-center text-sm text-red-600">PDF 证据加载失败，请检查报告文件。</p> : null}
        <iframe
          title="PDF 证据"
          className="min-h-0 flex-1"
          src={`${apiUrl(`/api/reports/${reportId}/file`)}#page=${page}&view=FitH`}
          onLoad={() => setIsLoading(false)}
          onError={showLoadError}
          onErrorCapture={showLoadError}
        />
      </div>
    </div>
  );
}
