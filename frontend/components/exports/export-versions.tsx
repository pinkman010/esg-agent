"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDown, FileCheck2 } from "lucide-react";
import { useState } from "react";
import {
  ApiError,
  exportFileUrl,
  generateExport,
  getReportDashboard,
  listExportVersions,
} from "@/lib/api";

const exportFormatLabels: Record<string, string> = {
  assessment_xlsx: "GRI 核查表（XLSX）",
  actions_xlsx: "整改任务清单（XLSX）",
  management_pdf: "管理层摘要（PDF）",
  print_html: "可打印核查表（HTML）",
};

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function exportGateMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const body = error.body as { detail?: { code?: string; remaining?: number } };
    const code = body.detail?.code;
    const remaining = body.detail?.remaining ?? 0;
    if (code === "analysis_incomplete") {
      return `正式输出被阻止：仍有 ${remaining} 条分析失败或未生成结果。`;
    }
    if (code === "high_risk_review_incomplete") {
      return `正式输出被阻止：仍有 ${remaining} 条高优先级项目未完成复核。`;
    }
  }
  return "输出生成失败，请检查分析与复核状态后重试。";
}

export function ExportVersions({ reportId, createdBy }: { reportId: string; createdBy: string }) {
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const query = useQuery({ queryKey: ["exports", reportId], queryFn: () => listExportVersions(reportId) });
  const dashboardQuery = useQuery({
    queryKey: ["report-dashboard", reportId],
    queryFn: () => getReportDashboard(reportId),
  });
  const mutation = useMutation({
    mutationFn: (draft: boolean) => generateExport(reportId, draft, createdBy),
    onMutate: () => setMessage(""),
    onSuccess: (result) => {
      setMessage(result.is_draft ? "草稿已生成" : `正式版本 v${result.version_number} 已生成`);
      client.invalidateQueries({ queryKey: ["exports", reportId] });
    },
  });
  const analysisIncomplete = dashboardQuery.data
    ? dashboardQuery.data.analysis_incomplete_count
      ?? dashboardQuery.data.failed_requirement_count
    : 0;
  const formalGate = dashboardQuery.isLoading
    ? { blocked: true, message: "正在读取正式输出门禁..." }
    : dashboardQuery.isError || !dashboardQuery.data
      ? { blocked: true, message: "正式输出门禁读取失败，请刷新页面后重试。" }
      : analysisIncomplete > 0
        ? {
            blocked: true,
            message: `正式输出暂不可用：仍有 ${analysisIncomplete} 条分析失败或未生成结果。`,
          }
        : dashboardQuery.data.high_priority_unresolved > 0
          ? {
              blocked: true,
              message: `正式输出暂不可用：仍有 ${dashboardQuery.data.high_priority_unresolved} 条高优先级项目未完成复核。`,
            }
          : { blocked: false, message: "当前预检通过；提交时仍由后端执行最终门禁校验。" };
  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <h2 className="text-sm font-semibold text-amber-950">输出门禁</h2>
        <p className="mt-2 text-sm leading-6 text-amber-900">
          草稿会保留全部待确认范围；正式输出要求分析完整且高优先级项目全部完成复核。
          高优先级复核完成不代表全部 577 项均已人工确认。
        </p>
        <p className="mt-2 text-sm font-medium text-amber-950">{formalGate.message}</p>
      </section>
      <div className="flex flex-wrap gap-2 rounded-xl border border-border bg-white p-4 shadow-sm">
        <button disabled={mutation.isPending} type="button" className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm font-medium disabled:opacity-50" onClick={() => mutation.mutate(true)}><FileDown aria-hidden="true" className="h-4 w-4" />生成草稿</button>
        <button disabled={mutation.isPending || formalGate.blocked} type="button" className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground disabled:opacity-50" onClick={() => mutation.mutate(false)}><FileCheck2 aria-hidden="true" className="h-4 w-4" />生成正式输出</button>
        {message && <span className="self-center text-sm text-emerald-700">{message}</span>}
        {mutation.isError && <span role="alert" className="self-center text-sm text-red-600">{exportGateMessage(mutation.error)}</span>}
      </div>
      {query.isLoading && <p className="py-6 text-sm text-muted-foreground">正在加载输出版本...</p>}
      {query.isError && <p role="alert" className="py-6 text-sm text-red-700">输出版本加载失败，请稍后重试。</p>}
      {query.data?.length === 0 && (
        <div className="rounded-xl border border-dashed border-border py-8 text-center">
          <p className="text-sm font-medium">尚未生成输出版本</p>
          <p className="mt-1 text-xs text-muted-foreground">可先生成带待确认标记的草稿。</p>
        </div>
      )}
      {query.data && query.data.length > 0 && (
      <div className="grid gap-4">
        {query.data.map((item) => (
          <article key={item.export_id} className="grid gap-3 rounded-xl border border-border bg-white p-4 shadow-sm sm:grid-cols-[1fr_auto]">
            <div>
              <p className="text-sm font-semibold">{item.is_draft ? "草稿" : `正式版本 v${item.version_number}`}</p>
              <p className="mt-1 text-xs text-muted-foreground">状态：{item.is_draft ? "草稿" : "正式输出"}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                创建人：{item.created_by}
                {item.created_at ? ` · ${new Date(item.created_at).toLocaleString("zh-CN")}` : ""}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">高优先级复核 {String(item.review_scope?.high_priority_reviewed ?? item.review_scope?.high_risk_reviewed ?? 0)}/{String(item.review_scope?.high_priority_total ?? item.review_scope?.high_risk_total ?? 0)}</p>
              <p className="mt-1 text-xs text-muted-foreground">中优先级未复核 {String(item.review_scope?.medium_priority_unresolved ?? 0)} · 适用性待判定 {String(item.review_scope?.applicability_undetermined_total ?? 0)}</p>
              {Number(item.review_scope?.analysis_incomplete_total ?? 0) > 0 && <p className="mt-1 text-xs text-red-600">分析失败或未生成结果 {String(item.review_scope?.analysis_incomplete_total)}</p>}
              {item.review_scope?.review_scope_statement ? <p className="mt-1 text-xs text-amber-700">{String(item.review_scope.review_scope_statement)}</p> : null}
            </div>
            <span className="text-xs text-muted-foreground">{item.file_manifest?.length ?? 0} 个文件</span>
            {item.file_manifest.length > 0 && (
              <ul className="grid gap-2 border-t border-border pt-3 sm:col-span-2 sm:grid-cols-2">
                {item.file_manifest.map((file) => {
                  const label = exportFormatLabels[file.format] ?? file.filename;
                  return (
                    <li key={file.file_id} className="flex items-center justify-between gap-3 rounded-md bg-muted/40 px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{label}</p>
                        <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                      </div>
                      <a
                        aria-label={`下载 ${label}`}
                        className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted"
                        download={file.filename}
                        href={exportFileUrl(item.export_id, file.file_id)}
                      >
                        <FileDown aria-hidden="true" className="h-3.5 w-3.5" />
                        下载
                      </a>
                    </li>
                  );
                })}
              </ul>
            )}
          </article>
        ))}
      </div>
      )}
    </div>
  );
}
