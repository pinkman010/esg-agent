"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { listRuns } from "@/lib/api";
export function RunsList() {
  const runsQuery = useQuery({ queryKey: ["runs"], queryFn: listRuns });
  if (runsQuery.isLoading) return <p className="rounded-lg border border-border bg-white p-5 text-sm text-muted-foreground">Loading runs.</p>;
  if (runsQuery.error) return <p className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">Runs failed to load.</p>;
  const runs = runsQuery.data ?? [];
  if (runs.length === 0) return <p className="rounded-lg border border-dashed border-border bg-white p-5 text-sm text-muted-foreground">No analysis runs.</p>;
  return <section className="rounded-lg border border-border bg-white p-5 shadow-sm"><h1 className="text-xl font-semibold tracking-normal">Runs</h1><div className="mt-4 divide-y divide-border">{runs.map((run) => <Link key={run.run_id} className="flex items-center justify-between gap-4 py-3 text-sm hover:text-accent" href={`/runs/${run.run_id}`}><span className="font-mono text-xs">{run.run_id}</span><span>{run.status}</span></Link>)}</div></section>;
}