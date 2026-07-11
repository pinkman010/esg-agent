import { ReviewerGate } from "@/components/review/reviewer-gate";

export default async function ReviewPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <ReviewerGate reportId={reportId} />;
}
