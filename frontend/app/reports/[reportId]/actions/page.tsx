import { ActionList } from "@/components/actions/action-list";
import { ReportPageHero } from "@/components/layout/report-page-hero";

export default async function ActionsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="披露改进闭环"
        title="整改任务"
        description="将人工复核确认的披露缺口转化为责任人、截止日期和状态可追踪的任务。"
        imageSrc="/visuals/module-claw-monitor.webp"
        imagePosition="42% 50%"
      />
      <div className="pt-5">
        <ActionList reportId={reportId} />
      </div>
    </div>
  );
}
