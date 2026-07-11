import { ReportUploadPanel } from "@/components/upload/report-upload-panel";
import { ReportList } from "@/components/reports/report-list";

export default function ReportsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">ESG 报告</h1>
        <p className="mt-1 text-sm text-muted-foreground">管理报告、确认信息并进入 GRI 核查。</p>
      </div>
      <div className="grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="min-w-0">
          <h2 className="mb-3 text-sm font-semibold">报告列表</h2>
          <ReportList />
        </section>
        <ReportUploadPanel />
      </div>
    </div>
  );
}
