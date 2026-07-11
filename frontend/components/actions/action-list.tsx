"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarDays, UserRound } from "lucide-react";
import { listActions } from "@/lib/api";

const statusLabels: Record<string, string> = { open: "待处理", in_progress: "进行中", completed: "已完成", cancelled: "已取消" };

export function ActionList({ reportId }: { reportId: string }) {
  const query = useQuery({ queryKey: ["actions", reportId], queryFn: () => listActions(reportId) });
  if (!query.data) return <p className="py-8 text-sm text-muted-foreground">正在加载整改任务...</p>;
  if (!query.data.length) return <p className="border-y border-border py-8 text-center text-sm text-muted-foreground">暂无整改任务。</p>;
  return <div className="divide-y divide-border border-y border-border">{query.data.map((action) => <article key={action.action_id} className="grid gap-3 py-4 md:grid-cols-[1fr_auto]"><div><div className="flex items-center gap-2"><h2 className="text-sm font-semibold">{action.title}</h2><span className="text-xs text-muted-foreground">{statusLabels[action.status] ?? action.status}</span></div><p className="mt-2 text-sm text-muted-foreground">{action.recommendation_text}</p></div><div className="space-y-1 text-xs text-muted-foreground">{action.owner_name && <p className="flex items-center gap-1"><UserRound className="h-3.5 w-3.5" />{action.owner_name}</p>}{action.due_date && <p className="flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{action.due_date}</p>}</div></article>)}</div>;
}
