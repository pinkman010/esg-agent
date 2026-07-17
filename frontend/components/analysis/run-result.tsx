"use client";

import { useQuery } from "@tanstack/react-query";
import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { AlertCircle, Download, RefreshCcw } from "lucide-react";
import { DisclosureSummaryChart } from "@/components/charts/disclosure-summary-chart";
import { apiUrl, getRun, listRunAssessments, listRunRecommendations } from "@/lib/api";
import { reviewStatusLabels } from "@/lib/business-labels";
import type { DisclosureAssessment } from "@/lib/types";

const columns: ColumnDef<DisclosureAssessment>[] = [
  { accessorKey: "disclosure_id", header: "Disclosure" },
  { accessorKey: "requirement_id", header: "Requirement" },
  { accessorKey: "verdict", header: "Verdict" },
  { accessorKey: "review_status", header: "Review", cell: ({ row }) => reviewStatusLabels[row.original.review_status] ?? "待确认" },
  { id: "evidence", header: "Evidence", cell: ({ row }) => { const evidence = row.original.evidence?.[0]; return evidence ? `${evidence.source_method} p.${evidence.source_page}` : "No evidence"; } },
];

export function RunResult({ runId }: { runId: string }) {
  const runQuery = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId), refetchInterval: 5000 });
  const assessmentsQuery = useQuery({ queryKey: ["run", runId, "assessments"], queryFn: () => listRunAssessments(runId) });
  const recommendationsQuery = useQuery({ queryKey: ["run", runId, "recommendations"], queryFn: () => listRunRecommendations(runId) });
  const assessments = assessmentsQuery.data ?? [];
  const recommendations = recommendationsQuery.data ?? [];
  const table = useReactTable({ data: assessments, columns, getCoreRowModel: getCoreRowModel() });

  if (runQuery.isLoading || assessmentsQuery.isLoading || recommendationsQuery.isLoading) return <div className="rounded-lg border border-border bg-white p-5 text-sm text-muted-foreground">Loading run data.</div>;
  if (runQuery.error || assessmentsQuery.error || recommendationsQuery.error) return <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700"><AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4" />Run data failed to load.</div>;
  const run = runQuery.data;

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-border bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div><p className="text-sm font-medium uppercase tracking-normal text-muted-foreground">Run</p><h1 className="mt-1 font-mono text-xl font-semibold tracking-normal">{runId}</h1><p className="mt-2 text-sm text-muted-foreground">Status: {run?.status ?? "unknown"}</p>{run?.error_message ? <p className="mt-2 text-sm text-red-700">{run.error_message}</p> : null}</div>
          <div className="flex flex-wrap gap-2">
            <a className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm" href={apiUrl(`/api/exports/runs/${runId}/assessments.csv`)}><Download aria-hidden="true" className="h-4 w-4" />Assessments CSV</a>
            <a className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm" href={apiUrl(`/api/exports/runs/${runId}/review.csv`)}><Download aria-hidden="true" className="h-4 w-4" />Review CSV</a>
          </div>
        </div>
      </section>
      <DisclosureSummaryChart assessments={assessments} />
      <section className="rounded-lg border border-border bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-base font-semibold tracking-normal">Assessments</h2><button className="inline-flex h-8 items-center gap-2 rounded-md border border-border px-3 text-sm" type="button" onClick={() => assessmentsQuery.refetch()}><RefreshCcw aria-hidden="true" className="h-4 w-4" />Refresh</button></div>
        {assessments.length === 0 ? <p className="text-sm text-muted-foreground">No assessments available.</p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[760px] border-collapse text-left text-sm"><thead>{table.getHeaderGroups().map((headerGroup) => <tr key={headerGroup.id} className="border-b border-border">{headerGroup.headers.map((header) => <th key={header.id} className="px-3 py-2 font-medium text-muted-foreground">{flexRender(header.column.columnDef.header, header.getContext())}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map((row) => <tr key={row.id} className="border-b border-border last:border-0">{row.getVisibleCells().map((cell) => <td key={cell.id} className="px-3 py-3 align-top">{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody></table></div>
        )}
      </section>
      <section className="rounded-lg border border-border bg-white p-5 shadow-sm"><h2 className="text-base font-semibold tracking-normal">Recommendations</h2>{recommendations.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">No recommendations available.</p> : <ul className="mt-3 space-y-2">{recommendations.map((item) => <li key={item.recommendation_id} className="rounded-md bg-muted p-3 text-sm">{item.recommendation_text}</li>)}</ul>}</section>
    </div>
  );
}
