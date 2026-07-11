"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDown, FileCheck2 } from "lucide-react";
import { useState } from "react";
import { generateExport, listExportVersions } from "@/lib/api";

export function ExportVersions({ reportId, createdBy }: { reportId: string; createdBy: string }) {
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const query = useQuery({ queryKey: ["exports", reportId], queryFn: () => listExportVersions(reportId) });
  const mutation = useMutation({ mutationFn: (draft: boolean) => generateExport(reportId, draft, createdBy), onSuccess: (result) => { setMessage(result.is_draft ? "草稿已生成" : `正式版本 v${result.version_number} 已生成`); client.invalidateQueries({ queryKey: ["exports", reportId] }); } });
  return <div><div className="flex flex-wrap gap-2"><button type="button" className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm font-medium" onClick={() => mutation.mutate(true)}><FileDown className="h-4 w-4" />生成草稿</button><button type="button" className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground" onClick={() => mutation.mutate(false)}><FileCheck2 className="h-4 w-4" />生成正式输出</button>{message && <span className="self-center text-sm text-emerald-700">{message}</span>}</div><div className="mt-6 divide-y divide-border border-y border-border">{(query.data ?? []).map((item) => <div key={item.export_id} className="grid gap-2 py-3 sm:grid-cols-[1fr_auto]"><div><p className="text-sm font-semibold">{item.is_draft ? "草稿" : `正式版本 v${item.version_number}`}</p><p className="mt-1 text-xs text-muted-foreground">高风险复核 {String(item.review_scope?.high_risk_reviewed ?? 0)}/{String(item.review_scope?.high_risk_total ?? 0)}</p></div><span className="text-xs text-muted-foreground">{item.file_manifest?.length ?? 0} 个文件</span></div>)}</div></div>;
}
