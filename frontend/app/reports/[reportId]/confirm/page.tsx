import { ReportMetadataConfirmation } from "@/components/reports/report-metadata-confirmation";

export default async function ConfirmReportPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <ReportMetadataConfirmation reportId={reportId} />;
}
