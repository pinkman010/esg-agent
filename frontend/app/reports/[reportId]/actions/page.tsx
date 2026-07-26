import { ActionList } from "@/components/actions/action-list";

export default async function ActionsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-7"><div className="border-b border-border pb-5"><p className="text-sm font-semibold text-emerald-700">披露改进闭环</p><h1 className="mt-1 text-2xl font-semibold">整改任务</h1><p className="mt-2 text-sm text-muted-foreground">将人工复核确认的披露缺口转化为责任人、截止日期和状态可追踪的任务。</p></div><div className="pt-5"><ActionList reportId={reportId} /></div></div>;
}
