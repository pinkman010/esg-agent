import { ExportVersions } from "@/components/exports/export-versions";

export default async function ExportsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-7"><div className="border-b border-border pb-5"><p className="text-sm font-semibold text-emerald-700">版本化交付</p><h1 className="mt-1 text-2xl font-semibold">输出与版本</h1><p className="mt-2 text-sm text-muted-foreground">生成带复核范围说明的草稿或正式版本，并保留版本、创建人和生成时间。</p></div><div className="pt-5"><ExportVersions reportId={reportId} createdBy="当前复核人" /></div></div>;
}
