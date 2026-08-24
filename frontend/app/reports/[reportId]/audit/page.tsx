import { ReportAuditTimeline } from "@/components/audit/report-audit-timeline";
import { ReportPageHero } from "@/components/layout/report-page-hero";

export default async function ReportAuditPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="报告留痕"
        title="审计时间线"
        description="汇总报告上传、分析、重跑、人工复核、整改和输出事件。技术敏感信息已从公开视图移除。"
        imageSrc="/visuals/module-claw-monitor.webp"
        imagePosition="42% 50%"
      />
      <div className="pt-5">
        <ReportAuditTimeline reportId={reportId} />
      </div>
    </div>
  );
}
