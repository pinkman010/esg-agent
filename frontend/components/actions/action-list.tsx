"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { getAssessmentDetail, listActions, updateAction } from "@/lib/api";
import type {
  ActionStatus,
  ImprovementAction,
  UpdateActionRequest,
} from "@/lib/types";

const statusLabels: Record<string, string> = { open: "待处理", in_progress: "进行中", completed: "已完成", cancelled: "已取消" };
const priorityLabels: Record<string, string> = { high: "高优先级", medium: "中优先级", low: "低优先级" };

function ActionItem({ action, reportId }: { action: ImprovementAction; reportId: string }) {
  const [status, setStatus] = useState<ActionStatus>(action.status);
  const [ownerName, setOwnerName] = useState(action.owner_name ?? "");
  const [dueDate, setDueDate] = useState(action.due_date ?? "");
  const [completionNote, setCompletionNote] = useState("");
  const [saved, setSaved] = useState(false);
  const queryClient = useQueryClient();
  const assessmentQuery = useQuery({
    queryKey: ["assessment-detail", reportId, action.assessment_id],
    queryFn: () => getAssessmentDetail(reportId, action.assessment_id),
  });
  const statusChanged = status !== action.status;
  const ownerChanged = ownerName.trim() !== (action.owner_name ?? "");
  const dueDateChanged = dueDate !== (action.due_date ?? "");
  const hasChanges = statusChanged || ownerChanged || dueDateChanged;
  const mutation = useMutation({
    mutationFn: () => {
      const payload: UpdateActionRequest = {};
      if (statusChanged) {
        payload.status = status;
        payload.completion_note = completionNote.trim() || null;
      }
      if (ownerChanged) {
        payload.owner_name = ownerName.trim() || null;
      }
      if (dueDateChanged) {
        payload.due_date = dueDate || null;
      }
      return updateAction(action.action_id, payload);
    },
    onMutate: () => setSaved(false),
    onSuccess: async () => {
      setSaved(true);
      setCompletionNote("");
      await queryClient.invalidateQueries({ queryKey: ["actions", reportId] });
    },
  });

  return (
    <article className="space-y-4 rounded-xl border border-border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-semibold">{action.title}</h2><span className="text-xs text-muted-foreground">{statusLabels[action.status] ?? action.status}</span><span className="text-xs text-muted-foreground">{priorityLabels[action.priority] ?? action.priority}</span></div>
          {assessmentQuery.data?.requirement_id && (
            <p className="mt-2 text-xs font-medium text-emerald-800">
              关联核查项：{assessmentQuery.data.requirement_id}
            </p>
          )}
          <p className="mt-2 text-sm text-muted-foreground">{action.recommendation_text}</p>
        </div>
        <div className="space-y-1 text-xs text-muted-foreground">{action.owner_name && <p className="flex items-center gap-1"><UserRound className="h-3.5 w-3.5" />{action.owner_name}</p>}{action.due_date && <p className="flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{action.due_date}</p>}</div>
      </div>
      <div className="grid gap-3 rounded-md bg-muted/50 p-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="text-xs font-medium">
          任务状态
          <select aria-label={`任务状态：${action.title}`} className="mt-1 h-9 w-full rounded-md border border-border bg-white px-2 font-normal" value={status} onChange={(event) => setStatus(event.target.value as ActionStatus)}>
            <option value="open">待处理</option>
            <option value="in_progress">进行中</option>
            <option value="completed">已完成</option>
            <option value="cancelled">已取消</option>
          </select>
        </label>
        <label className="text-xs font-medium">
          负责人
          <input aria-label={`负责人：${action.title}`} className="mt-1 h-9 w-full rounded-md border border-border px-2 font-normal" value={ownerName} onChange={(event) => setOwnerName(event.target.value)} />
        </label>
        <label className="text-xs font-medium">
          截止日期
          <input aria-label={`截止日期：${action.title}`} className="mt-1 h-9 w-full rounded-md border border-border px-2 font-normal" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
        </label>
        <label className="text-xs font-medium">
          状态变更说明
          <input aria-label={`状态变更说明：${action.title}`} className="mt-1 h-9 w-full rounded-md border border-border px-2 font-normal" value={completionNote} onChange={(event) => setCompletionNote(event.target.value)} />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="inline-flex h-9 items-center rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50" disabled={!hasChanges || (statusChanged && !completionNote.trim()) || mutation.isPending} onClick={() => mutation.mutate()}>保存任务更新</button>
        {saved && <span className="text-sm text-emerald-700">任务已更新</span>}
        {mutation.isError && <span role="alert" className="text-sm text-red-600">任务更新失败，请重试。</span>}
      </div>
    </article>
  );
}

export function ActionList({ reportId }: { reportId: string }) {
  const query = useQuery({ queryKey: ["actions", reportId], queryFn: () => listActions(reportId) });
  if (query.isLoading) return <p className="py-8 text-sm text-muted-foreground">正在加载整改任务...</p>;
  if (query.isError) return <p role="alert" className="py-8 text-sm text-red-600">整改任务加载失败，请稍后重试。</p>;
  if (!query.data?.length) return <div className="border-y border-border py-8 text-center text-sm text-muted-foreground"><p>暂无整改任务。</p><Link className="mt-3 inline-block font-medium text-accent" href={`/reports/${reportId}/review`}>从复核工作台创建任务</Link></div>;
  const completed = query.data.filter((action) => action.status === "completed").length;
  const inProgress = query.data.filter((action) => action.status === "in_progress").length;
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-slate-100 px-3 py-1.5">共 {query.data.length} 项</span>
        <span className="rounded-full bg-blue-50 px-3 py-1.5 text-blue-800">进行中 {inProgress}</span>
        <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-emerald-800">已完成 {completed}</span>
      </div>
      <div className="grid gap-4">{query.data.map((action) => <ActionItem key={action.action_id} action={action} reportId={reportId} />)}</div>
    </div>
  );
}
