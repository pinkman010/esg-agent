"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertCircle, FileUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, uploadReport } from "@/lib/api";
import type { DuplicateReportDetail } from "@/lib/types";

function duplicateReportDetail(error: unknown): DuplicateReportDetail | null {
  if (!(error instanceof ApiError) || error.status !== 409 || typeof error.body !== "object" || error.body === null) return null;
  const detail = "detail" in error.body ? error.body.detail : null;
  if (typeof detail !== "object" || detail === null) return null;
  const code = "code" in detail ? detail.code : null;
  const reportId = "report_id" in detail ? detail.report_id : null;
  if (code !== "duplicate_report" || typeof reportId !== "string" || !reportId) return null;
  const message = "message" in detail && typeof detail.message === "string" ? detail.message : "相同报告已存在";
  const status = "existing_report_status" in detail && typeof detail.existing_report_status === "string"
    ? detail.existing_report_status as DuplicateReportDetail["existing_report_status"]
    : "uploaded";
  return {
    code,
    message,
    report_id: reportId,
    existing_report_status: status,
    can_start_new_demo: "can_start_new_demo" in detail && detail.can_start_new_demo === true,
  };
}

function errorMessage(error: unknown): string {
  return error ? "上传失败，请稍后重试。" : "";
}

export function ReportUploadPanel() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [reuploadError, setReuploadError] = useState<string | null>(null);
  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadReport(file),
    onSuccess: (report) => router.push(`/reports/${report.report_id}/confirm`),
  });
  const reuploadMutation = useMutation({
    mutationFn: (file: File) => uploadReport(file, "create_new"),
    onSuccess: (report) => router.push(`/reports/${report.report_id}/confirm`),
    onError: () => setReuploadError("重新上传失败，已有报告和历史结果未受影响，请重试。"),
  });
  const duplicateReport = duplicateReportDetail(uploadMutation.error);
  const isPending = uploadMutation.isPending || reuploadMutation.isPending;

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
            onChange={(event) => {
              setSelectedFile(event.currentTarget.files?.[0] ?? null);
              setReuploadError(null);
              uploadMutation.reset();
              reuploadMutation.reset();
            }}
          />
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!selectedFile || isPending}
            type="button"
            onClick={() => selectedFile && uploadMutation.mutate(selectedFile)}
          >
            <FileUp aria-hidden="true" className="h-4 w-4" />
            上传 PDF
          </button>
          {uploadMutation.error && (
            <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4" />
              {duplicateReport ? (
                <div className="space-y-2">
                  <p>报告已存在</p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="rounded-md border border-red-300 bg-white px-3 py-1.5 font-medium text-red-700"
                      type="button"
                      onClick={() => router.push(`/reports/${duplicateReport.report_id}/dashboard`)}
                    >
                      查看已有结果
                    </button>
                    <button
                      className="rounded-md border border-red-300 bg-white px-3 py-1.5 font-medium text-red-700"
                      disabled={isPending || !selectedFile}
                      type="button"
                      onClick={() => {
                        if (!selectedFile) return;
                        setReuploadError(null);
                        reuploadMutation.mutate(selectedFile);
                      }}
                    >
                      {reuploadMutation.isPending ? "正在重新上传..." : "重新上传并分析"}
                    </button>
                  </div>
                  {reuploadError && <p role="alert">{reuploadError}</p>}
                </div>
              ) : (
                <span>{errorMessage(uploadMutation.error)}</span>
              )}
            </div>
          )}
      </div>
    </section>
  );
}
