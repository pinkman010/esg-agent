"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, FileUp, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { analyzeReport, uploadReport } from "@/lib/api";
import type { ReportUploadResponse } from "@/lib/types";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}

export function ReportUploadPanel() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedReport, setUploadedReport] = useState<ReportUploadResponse | null>(null);
  const [confirmLlm, setConfirmLlm] = useState(false);

  const uploadMutation = useMutation({ mutationFn: uploadReport, onSuccess: setUploadedReport });
  const analyzeMutation = useMutation({
    mutationFn: ({ reportId, allowModel }: { reportId: string; allowModel: boolean }) => analyzeReport(reportId, allowModel),
    onSuccess: (run) => router.push(`/runs/${run.run_id}`),
  });

  return (
    <section className="rounded-lg border border-border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-semibold tracking-normal">Reports</h1>
          <p className="mt-1 text-sm text-muted-foreground">No report is active until upload completes.</p>
        </div>
        <FileUp aria-hidden="true" className="h-5 w-5 text-accent" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <label className="block text-sm font-medium" htmlFor="pdf-report">PDF report</label>
          <input
            id="pdf-report"
            aria-label="PDF report"
            accept="application/pdf,.pdf"
            className="block w-full rounded-md border border-border bg-white px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm file:font-medium"
            type="file"
            onChange={(event) => { setSelectedFile(event.currentTarget.files?.[0] ?? null); setUploadedReport(null); }}
          />
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!selectedFile || uploadMutation.isPending}
            type="button"
            onClick={() => selectedFile && uploadMutation.mutate(selectedFile)}
          >
            <FileUp aria-hidden="true" className="h-4 w-4" />
            Upload PDF
          </button>
          {(uploadMutation.error || analyzeMutation.error) && (
            <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4" />
              <span>{errorMessage(uploadMutation.error ?? analyzeMutation.error)}</span>
            </div>
          )}
        </div>
        <div className="rounded-lg border border-border bg-muted p-4">
          <h2 className="text-sm font-semibold tracking-normal">Uploaded report</h2>
          {uploadedReport ? (
            <dl className="mt-3 space-y-3 text-sm">
              <div><dt className="text-muted-foreground">Report ID</dt><dd className="font-mono text-xs text-foreground">{uploadedReport.report_id}</dd></div>
              <div><dt className="text-muted-foreground">File hash</dt><dd className="break-all font-mono text-xs text-foreground">{uploadedReport.file_hash}</dd></div>
            </dl>
          ) : <p className="mt-3 text-sm text-muted-foreground">No report uploaded.</p>}
        </div>
      </div>
      <div className="mt-5 flex flex-col gap-4 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        <label className="inline-flex items-center gap-2 text-sm">
          <input aria-label="Allow external model call" checked={confirmLlm} className="h-4 w-4 accent-emerald-700" type="checkbox" onChange={(event) => setConfirmLlm(event.currentTarget.checked)} />
          Allow external model call
        </label>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-white px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!uploadedReport || analyzeMutation.isPending}
          type="button"
          onClick={() => uploadedReport && analyzeMutation.mutate({ reportId: uploadedReport.report_id, allowModel: confirmLlm })}
        >
          {analyzeMutation.isPending ? <CheckCircle2 aria-hidden="true" className="h-4 w-4" /> : <Play aria-hidden="true" className="h-4 w-4" />}
          Start analysis
        </button>
      </div>
    </section>
  );
}