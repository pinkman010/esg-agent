"use client";

import { useQuery } from "@tanstack/react-query";
import { listAuditRuns } from "@/lib/api";

export function AuditLog() {
  const auditQuery = useQuery({ queryKey: ["audit-runs"], queryFn: listAuditRuns });
  if (auditQuery.isLoading) return <p className="rounded-lg border border-border bg-white p-5 text-sm text-muted-foreground">Loading audit data.</p>;
  if (auditQuery.error) return <p className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">Audit data failed to load.</p>;
  const runs = auditQuery.data ?? [];
  if (runs.length === 0) return <p className="rounded-lg border border-dashed border-border bg-white p-5 text-sm text-muted-foreground">No audit events.</p>;
  return <section className="rounded-lg border border-border bg-white p-5 shadow-sm"><h1 className="text-xl font-semibold tracking-normal">Audit</h1><div className="mt-4 space-y-4">{runs.map((run) => <article key={run.run_id} className="rounded-lg border border-border p-4"><div className="grid gap-3 text-sm md:grid-cols-4"><div><p className="text-muted-foreground">Run</p><p className="font-mono text-xs">{run.run_id}</p></div><div><p className="text-muted-foreground">File hash</p><p className="break-all font-mono text-xs">{run.file_hash}</p></div><div><p className="text-muted-foreground">Model call</p><p>{run.model_called ? "confirmed" : "not_called"}</p></div><div><p className="text-muted-foreground">Status</p><p>{run.status}</p></div></div>{run.error_message ? <p className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{run.error_message}</p> : null}{run.events.length === 0 ? <p className="mt-3 text-sm text-muted-foreground">No events for this run.</p> : <ul className="mt-3 space-y-2">{run.events.map((event) => <li key={event.audit_event_id} className="rounded-md bg-muted p-3 text-sm"><div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"><span className="font-medium">{event.event_type}</span><span className="font-mono text-xs text-muted-foreground">{event.created_at ?? "pending"}</span></div><pre className="mt-2 overflow-auto rounded-md bg-white p-2 text-xs">{JSON.stringify(event.payload, null, 2)}</pre></li>)}</ul>}</article>)}</div></section>;
}