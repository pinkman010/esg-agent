import { ReportDashboard } from "@/components/analysis/report-dashboard";

export default async function DashboardPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <ReportDashboard reportId={reportId} />;
}
