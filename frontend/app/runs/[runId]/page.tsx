import { RunResult } from "@/components/analysis/run-result";

export default async function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <div className="mx-auto w-full max-w-6xl px-6 py-6"><RunResult runId={runId} /></div>;
}