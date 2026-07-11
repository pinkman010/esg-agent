import { AssessmentTable } from "@/components/analysis/assessment-table";

export default async function AssessmentsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <div className="mx-auto w-full max-w-7xl px-6 py-6"><AssessmentTable reportId={reportId} /></div>;
}
