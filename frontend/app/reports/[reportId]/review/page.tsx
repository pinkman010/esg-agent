import { ReviewerGate } from "@/components/review/reviewer-gate";

export default async function ReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ reportId: string }>;
  searchParams: Promise<{ assessmentId?: string | string[] }>;
}) {
  const { reportId } = await params;
  const query = await searchParams;
  const initialAssessmentId = typeof query.assessmentId === "string" && query.assessmentId.trim()
    ? query.assessmentId
    : undefined;
  return <ReviewerGate reportId={reportId} initialAssessmentId={initialAssessmentId} />;
}
