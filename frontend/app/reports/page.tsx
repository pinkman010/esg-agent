import { ReportUploadPanel } from "@/components/upload/report-upload-panel";
import { ReportList } from "@/components/reports/report-list";

export default function ReportsPage() {
  return (
    <div className="mx-auto w-full max-w-7xl px-5 py-6 lg:px-7">
      <div className="mb-7 border-b border-border pb-5">
        <p className="text-sm font-semibold text-emerald-700">报告工作区</p>
        <h1 className="mt-1 text-2xl font-semibold">ESG 报告</h1>
        <p className="mt-2 text-sm text-muted-foreground">上传报告、确认信息，并从当前业务状态继续 GRI 核查。</p>
      </div>
      <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="min-w-0">
          <h2 className="mb-3 text-base font-semibold">报告列表</h2>
          <ReportList />
        </section>
        <ReportUploadPanel />
      </div>
    </div>
  );
}
