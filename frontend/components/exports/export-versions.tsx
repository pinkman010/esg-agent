"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDown, FileCheck2 } from "lucide-react";
import { useState } from "react";
import { ApiError, generateExport, listExportVersions } from "@/lib/api";

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
  const mutation = useMutation({
    mutationFn: (draft: boolean) => generateExport(reportId, draft, createdBy),
    onMutate: () => setMessage(""),
    onSuccess: (result) => {
      setMessage(result.is_draft ? "草稿已生成" : `正式版本 v${result.version_number} 已生成`);
      client.invalidateQueries({ queryKey: ["exports", reportId] });
    },
  });
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm font-medium" onClick={() => mutation.mutate(true)}><FileDown className="h-4 w-4" />生成草稿</button>
        <button type="button" className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground" onClick={() => mutation.mutate(false)}><FileCheck2 className="h-4 w-4" />生成正式输出</button>
        {message && <span className="self-center text-sm text-emerald-700">{message}</span>}
        {mutation.isError && <span className="self-center text-sm text-red-600">{exportGateMessage(mutation.error)}</span>}
      </div>
      <div className="mt-6 divide-y divide-border border-y border-border">
        {(query.data ?? []).map((item) => (
          <div key={item.export_id} className="grid gap-2 py-3 sm:grid-cols-[1fr_auto]">
            <div>
              <p className="text-sm font-semibold">{item.is_draft ? "草稿" : `正式版本 v${item.version_number}`}</p>
              <p className="mt-1 text-xs text-muted-foreground">高优先级复核 {String(item.review_scope?.high_priority_reviewed ?? item.review_scope?.high_risk_reviewed ?? 0)}/{String(item.review_scope?.high_priority_total ?? item.review_scope?.high_risk_total ?? 0)}</p>
              <p className="mt-1 text-xs text-muted-foreground">中优先级未复核 {String(item.review_scope?.medium_priority_unresolved ?? 0)} · 适用性待判定 {String(item.review_scope?.applicability_undetermined_total ?? 0)}</p>
              {Number(item.review_scope?.analysis_incomplete_total ?? 0) > 0 && <p className="mt-1 text-xs text-red-600">分析失败或未生成结果 {String(item.review_scope?.analysis_incomplete_total)}</p>}
              {item.review_scope?.review_scope_statement ? <p className="mt-1 text-xs text-amber-700">{String(item.review_scope.review_scope_statement)}</p> : null}
            </div>
            <span className="text-xs text-muted-foreground">{item.file_manifest?.length ?? 0} 个文件</span>
          </div>
        ))}
      </div>
    </div>
  );
}
