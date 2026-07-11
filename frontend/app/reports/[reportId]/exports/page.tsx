import { ExportVersions } from "@/components/exports/export-versions";

export default async function ExportsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <div className="mx-auto w-full max-w-5xl px-6 py-6"><div className="border-b border-border pb-5"><h1 className="text-xl font-semibold">输出与版本</h1><p className="mt-1 text-sm text-muted-foreground">草稿会标记待确认范围；正式输出要求全部高风险项完成复核。</p></div><div className="pt-5"><ExportVersions reportId={reportId} createdBy="当前复核人" /></div></div>;
}
