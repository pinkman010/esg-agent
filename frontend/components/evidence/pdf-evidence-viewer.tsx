"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Maximize2, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiUrl, getReport } from "@/lib/api";

export function PdfEvidenceViewer({ reportId, initialPage = 1 }: { reportId: string; initialPage?: number }) {
  const [page, setPage] = useState(initialPage);
  const [zoom, setZoom] = useState(100);
  const [retryKey, setRetryKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const mounted = useRef(false);
  const reportQuery = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => getReport(reportId),
  });
  const pageCount = reportQuery.data?.page_count ?? null;

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    setPage(initialPage);
    setZoom(100);
    setRetryKey(0);
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

  function retryLoad() {
    setRetryKey((current) => current + 1);
    setIsLoading(true);
    setLoadFailed(false);
  }

  const imageSrc = `${apiUrl(`/api/reports/${reportId}/pages/${page}/image`)}?view=${retryKey}`;

  return (
    <div className="flex h-full min-h-[520px] flex-col bg-neutral-100">
      <div className="flex min-h-11 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-white px-3 py-1.5">
        <span className="text-sm font-medium">PDF 第 {page} 页</span>
        <div className="flex gap-1">
          <button aria-label="缩小 PDF" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" disabled={zoom <= 75} onClick={() => setZoom((current) => Math.max(75, current - 25))}><ZoomOut aria-hidden="true" className="h-4 w-4" /></button>
          <button aria-label="放大 PDF" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" disabled={zoom >= 200} onClick={() => setZoom((current) => Math.min(200, current + 25))}><ZoomIn aria-hidden="true" className="h-4 w-4" /></button>
          <button aria-label="恢复适合宽度" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" onClick={() => setZoom(100)}><Maximize2 aria-hidden="true" className="h-4 w-4" /></button>
          <button aria-label="上一页" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" disabled={page <= 1} onClick={() => changePage(Math.max(1, page - 1))}><ChevronLeft aria-hidden="true" className="h-4 w-4" /></button>
          <button aria-label="下一页" className="grid h-8 w-8 place-items-center rounded-md border border-border" type="button" disabled={pageCount !== null && page >= pageCount} onClick={() => changePage(pageCount === null ? page + 1 : Math.min(pageCount, page + 1))}><ChevronRight aria-hidden="true" className="h-4 w-4" /></button>
        </div>
      </div>
      <div className="relative min-h-0 flex-1 overflow-auto">
        {isLoading && !loadFailed ? <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">正在加载 PDF 证据...</p> : null}
        {loadFailed ? (
          <div role="alert" className="absolute inset-0 z-10 grid place-items-center px-6 text-center text-sm text-red-600">
            <div>
              <p>PDF 证据加载失败，请检查报告文件。</p>
              <button type="button" className="mt-3 inline-flex items-center gap-2 rounded-md border border-red-200 bg-white px-3 py-2 font-medium" onClick={retryLoad}>
                <RotateCcw aria-hidden="true" className="h-4 w-4" />
                重试加载 PDF 证据
              </button>
            </div>
          </div>
        ) : null}
        <img
          key={`${reportId}-${page}-${retryKey}`}
          title="PDF 证据"
          alt={`PDF 第 ${page} 页证据`}
          className={`mx-auto h-auto max-w-none object-contain object-top ${loadFailed ? "opacity-0" : ""}`}
          style={{ width: `${zoom}%` }}
          src={imageSrc}
          onLoad={() => setIsLoading(false)}
          onError={showLoadError}
        />
      </div>
    </div>
  );
}
