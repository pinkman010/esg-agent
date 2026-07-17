"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, PencilLine, X } from "lucide-react";
import { useEffect, useState } from "react";
import { listReviewAssessments, listReviewRuns, saveReviewDecision } from "@/lib/api";
import { reviewStatusLabels } from "@/lib/business-labels";
import type { ReviewStatus } from "@/lib/types";

const filters: Array<ReviewStatus | "all"> = ["all", "needs_manual_review", "approved", "rejected", "corrected"];

export function ReviewWorkbench() {
  const queryClient = useQueryClient();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [filter, setFilter] = useState<ReviewStatus | "all">("all");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [savedStatus, setSavedStatus] = useState<Record<string, ReviewStatus>>({});
  const runsQuery = useQuery({ queryKey: ["review-runs"], queryFn: listReviewRuns });
  const assessmentsQuery = useQuery({ queryKey: ["review-assessments", selectedRunId], queryFn: () => listReviewAssessments(selectedRunId ?? ""), enabled: selectedRunId !== null });
  const decisionMutation = useMutation({
    mutationFn: ({ assessmentId, status }: { assessmentId: string; status: ReviewStatus }) => saveReviewDecision(selectedRunId ?? "", { assessment_id: assessmentId, review_status: status, reviewer_note: notes[assessmentId] ?? "" }),
    onSuccess: (decision) => {
      setSavedStatus((current) => ({ ...current, [decision.assessment_id]: decision.review_status }));
      queryClient.invalidateQueries({ queryKey: ["review-runs"] });
      queryClient.invalidateQueries({ queryKey: ["review-assessments", selectedRunId] });
    },
  });
  useEffect(() => { const firstRun = runsQuery.data?.[0]; if (!selectedRunId && firstRun) setSelectedRunId(firstRun.run_id); }, [runsQuery.data, selectedRunId]);
  if (runsQuery.isLoading) return <p className="rounded-lg border border-border bg-white p-5 text-sm text-muted-foreground">Loading review queue.</p>;
  if (runsQuery.error) return <p className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">Review queue failed to load.</p>;
  const runs = runsQuery.data ?? [];
  if (runs.length === 0) return <p className="rounded-lg border border-dashed border-border bg-white p-5 text-sm text-muted-foreground">No runs need manual review.</p>;
  const assessments = (assessmentsQuery.data ?? []).filter((assessment) => filter === "all" || assessment.review_status === filter);
  return (
    <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
      <section className="rounded-lg border border-border bg-white p-4 shadow-sm"><h1 className="text-lg font-semibold tracking-normal">Review</h1><div className="mt-4 space-y-2">{runs.map((run) => <button key={run.run_id} className="flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted data-[active=true]:bg-muted" data-active={run.run_id === selectedRunId} type="button" onClick={() => setSelectedRunId(run.run_id)}><span className="truncate font-mono text-xs">{run.run_id}</span><span>{run.status}</span></button>)}</div></section>
      <section className="rounded-lg border border-border bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between"><h2 className="text-base font-semibold tracking-normal">Assessments</h2><select className="h-9 rounded-md border border-border bg-white px-3 text-sm" value={filter} onChange={(event) => setFilter(event.currentTarget.value as ReviewStatus | "all")}>{filters.map((item) => <option key={item} value={item}>{item === "all" ? "全部" : reviewStatusLabels[item] ?? "待确认"}</option>)}</select></div>
        {assessmentsQuery.isLoading ? <p className="mt-4 text-sm text-muted-foreground">Loading assessments.</p> : null}
        {assessments.length === 0 && !assessmentsQuery.isLoading ? <p className="mt-4 text-sm text-muted-foreground">No assessments match the current filter.</p> : null}
        <div className="mt-4 space-y-3">{assessments.map((assessment) => <article key={assessment.assessment_id} className="rounded-lg border border-border p-4"><div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between"><div><h3 className="font-medium tracking-normal">{assessment.disclosure_id}</h3><p className="mt-1 text-sm text-muted-foreground">{assessment.rationale}</p>{savedStatus[assessment.assessment_id] ? <p className="mt-2 text-sm text-accent">已保存：{reviewStatusLabels[savedStatus[assessment.assessment_id]] ?? "待确认"}</p> : null}</div><div className="flex flex-wrap gap-2"><button className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm" type="button" onClick={() => decisionMutation.mutate({ assessmentId: assessment.assessment_id, status: "approved" })}><Check aria-hidden="true" className="h-4 w-4" />Approve</button><button className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm" type="button" onClick={() => decisionMutation.mutate({ assessmentId: assessment.assessment_id, status: "rejected" })}><X aria-hidden="true" className="h-4 w-4" />Reject</button><button className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm" type="button" onClick={() => decisionMutation.mutate({ assessmentId: assessment.assessment_id, status: "corrected" })}><PencilLine aria-hidden="true" className="h-4 w-4" />Correct</button></div></div><textarea aria-label={`Reviewer note for ${assessment.assessment_id}`} className="mt-3 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm" value={notes[assessment.assessment_id] ?? ""} onChange={(event) => setNotes((current) => ({ ...current, [assessment.assessment_id]: event.currentTarget.value }))} /></article>)}</div>
      </section>
    </div>
  );
}
