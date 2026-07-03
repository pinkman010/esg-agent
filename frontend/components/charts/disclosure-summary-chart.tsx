"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { AssessmentVerdict } from "@/lib/types";

type AssessmentLike = { verdict: AssessmentVerdict };
const verdicts: AssessmentVerdict[] = ["disclosed", "partially_disclosed", "not_disclosed", "unknown"];

export function DisclosureSummaryChart({ assessments }: { assessments: AssessmentLike[] }) {
  const data = verdicts.map((verdict) => ({ verdict, count: assessments.filter((assessment) => assessment.verdict === verdict).length }));
  if (assessments.length === 0) {
    return <section className="rounded-lg border border-dashed border-border bg-white p-5"><h2 className="text-base font-semibold tracking-normal">Disclosure summary</h2><p className="mt-2 text-sm text-muted-foreground">No assessments to chart.</p></section>;
  }
  return (
    <section className="rounded-lg border border-border bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-1"><h2 className="text-base font-semibold tracking-normal">Disclosure summary</h2><p className="text-sm text-muted-foreground">Verdict totals from current assessments.</p></div>
      <div className="mt-4 h-56 w-full">
        <ResponsiveContainer height="100%" width="100%">
          <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="verdict" tick={{ fontSize: 11 }} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} tickLine={false} width={28} />
            <Tooltip />
            <Bar dataKey="count" fill="hsl(var(--accent))" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <dl className="mt-4 grid gap-2 sm:grid-cols-4">
        {data.map((item) => <div key={item.verdict} className="rounded-md bg-muted px-3 py-2"><dt className="truncate text-xs text-muted-foreground">{item.verdict}</dt><dd className="font-mono text-lg font-semibold">{item.count}</dd></div>)}
      </dl>
    </section>
  );
}