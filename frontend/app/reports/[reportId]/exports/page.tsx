import { ExportVersions } from "@/components/exports/export-versions";
import { ReportPageHero } from "@/components/layout/report-page-hero";

export default async function ExportsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="版本化交付"
        title="输出与版本"
        description="生成带复核范围说明的草稿或正式版本，并保留版本、创建人和生成时间。"
        imageSrc="/visuals/module-policy-disclosure.webp"
        imagePosition="28% 50%"
      />
      <div className="pt-5">
        <ExportVersions reportId={reportId} createdBy="当前复核人" />
      </div>
    </div>
  );
}
