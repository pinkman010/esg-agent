import { ReportAuditTimeline } from "@/components/audit/report-audit-timeline";

export default async function ReportAuditPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-6 lg:px-7">
      <ReportAuditTimeline reportId={reportId} />
    </div>
  );
}
