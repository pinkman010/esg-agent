import { AnalysisProgress } from "@/components/analysis/analysis-progress";

export default async function ReportProgressPage({
  params,
  searchParams,
}: {
  params: Promise<{ reportId: string }>;
  searchParams: Promise<{ runId?: string }>;
}) {
  const [{ reportId }, query] = await Promise.all([params, searchParams]);
  if (!query.runId) return <p className="p-6 text-sm text-red-700">缺少分析运行标识。</p>;
  return <AnalysisProgress reportId={reportId} runId={query.runId} />;
}
