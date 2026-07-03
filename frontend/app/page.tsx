import { ArrowRight, Database, FileText, ShieldCheck } from "lucide-react";
import Link from "next/link";

const workflow = [
  { label: "Upload", detail: "PDF report intake", icon: FileText },
  { label: "Analyze", detail: "GRI disclosure run", icon: Database },
  { label: "Review", detail: "Evidence decisions", icon: ShieldCheck },
];

export default function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-6">
      <section className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="text-sm font-medium uppercase tracking-normal text-muted-foreground">Workspace</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-foreground">ESG disclosure analysis</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
            No report has been selected in this session.
          </p>
        </div>
        <Link
          href="/reports"
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground shadow-sm transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
        >
          Open reports
          <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {workflow.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="min-h-32 rounded-lg border border-border bg-white p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-muted text-accent">
                  <Icon aria-hidden="true" className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="text-base font-semibold tracking-normal">{item.label}</h2>
                  <p className="text-sm text-muted-foreground">{item.detail}</p>
                </div>
              </div>
            </div>
          );
        })}
      </section>

      <section className="rounded-lg border border-dashed border-border bg-white p-6">
        <h2 className="text-lg font-semibold tracking-normal">Current run</h2>
        <p className="mt-2 text-sm text-muted-foreground">No active analysis run.</p>
      </section>
    </div>
  );
}