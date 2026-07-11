import { ActionList } from "@/components/actions/action-list";

export default async function ActionsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <div className="mx-auto w-full max-w-5xl px-6 py-6"><div className="border-b border-border pb-5"><h1 className="text-xl font-semibold">整改任务</h1><p className="mt-1 text-sm text-muted-foreground">跟踪披露缺口的整改责任和完成情况。</p></div><div className="pt-5"><ActionList reportId={reportId} /></div></div>;
}
