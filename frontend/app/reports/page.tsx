import { ReportPageHero } from "@/components/layout/report-page-hero";
import { ReportUploadPanel } from "@/components/upload/report-upload-panel";
import { ReportList } from "@/components/reports/report-list";

export default function ReportsPage() {
  return (
    <div className="mx-auto w-full max-w-7xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="报告工作区"
        title="ESG 报告"
        description="上传报告、确认信息，并从当前业务状态继续 GRI 核查。"
        imageSrc="/visuals/module-policy-disclosure.webp"
      />
      <div className="mt-7 grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="min-w-0">
          <h2 className="mb-3 text-base font-semibold">报告列表</h2>
          <ReportList />
        </section>
        <ReportUploadPanel />
      </div>
    </div>
  );
}
