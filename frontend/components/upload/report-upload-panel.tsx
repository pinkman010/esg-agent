"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertCircle, FileUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { uploadReport } from "@/lib/api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "上传失败，请稍后重试。";
}

export function ReportUploadPanel() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const uploadMutation = useMutation({
    mutationFn: uploadReport,
    onSuccess: (report) => router.push(`/reports/${report.report_id}/confirm`),
  });

  return (
    <section className="min-w-0 rounded-lg border border-border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-base font-semibold tracking-normal">上传 ESG 报告</h2>
          <p className="mt-1 text-sm text-muted-foreground">上传 PDF 后先确认企业、年度和语言，再启动分析。</p>
        </div>
        <FileUp aria-hidden="true" className="h-5 w-5 text-accent" />
      </div>
      <div className="mt-5 space-y-4">
          <label className="block text-sm font-medium" htmlFor="pdf-report">PDF 报告文件</label>
          <input
            id="pdf-report"
            aria-label="PDF 报告文件"
            accept="application/pdf,.pdf"
            className="block w-full min-w-0 max-w-full rounded-md border border-border bg-white px-3 py-2 text-sm file:mr-2 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm file:font-medium"
            type="file"
            onChange={(event) => setSelectedFile(event.currentTarget.files?.[0] ?? null)}
          />
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!selectedFile || uploadMutation.isPending}
            type="button"
            onClick={() => selectedFile && uploadMutation.mutate(selectedFile)}
          >
            <FileUp aria-hidden="true" className="h-4 w-4" />
            上传 PDF
          </button>
          {uploadMutation.error && (
            <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4" />
              <span>{errorMessage(uploadMutation.error)}</span>
            </div>
          )}
      </div>
    </section>
  );
}
