"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { createAction } from "@/lib/api";
import type { ActionPriority } from "@/lib/types";

export function ActionCreator({
  reportId,
  assessmentId,
  requirementId,
  reviewerName,
  missingItems,
}: {
  reportId: string;
  assessmentId: string;
  requirementId: string;
  reviewerName: string;
  missingItems: string[];
}) {
  const defaultRecommendation = missingItems.length
    ? `补充以下内容：${missingItems.join("；")}`
    : `补充 ${requirementId} 所需的实质性披露。`;
  const [title, setTitle] = useState(`补充 ${requirementId} 披露缺口`);
  const [priority, setPriority] = useState<ActionPriority>("high");
  const [ownerName, setOwnerName] = useState(reviewerName);
  const [dueDate, setDueDate] = useState("");
  const [recommendationText, setRecommendationText] = useState(defaultRecommendation);
  const [created, setCreated] = useState(false);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => createAction(reportId, {
      assessment_id: assessmentId,
      title: title.trim(),
      priority,
      owner_name: ownerName.trim() || null,
      due_date: dueDate || null,
      recommendation_text: recommendationText.trim(),
      created_by: reviewerName,
    }),
    onMutate: () => setCreated(false),
    onSuccess: async () => {
      setCreated(true);
      await queryClient.invalidateQueries({ queryKey: ["actions", reportId] });
    },
  });

  return (
    <section className="border-t border-border pt-4">
      <h3 className="text-sm font-semibold">创建整改任务</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-medium sm:col-span-2">
          任务标题
          <input aria-label="任务标题" className="mt-1 h-9 w-full rounded-md border border-border px-3 font-normal" value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label className="text-xs font-medium">
          优先级
          <select aria-label="整改任务优先级" className="mt-1 h-9 w-full rounded-md border border-border bg-white px-3 font-normal" value={priority} onChange={(event) => setPriority(event.target.value as ActionPriority)}>
            <option value="high">高</option>
            <option value="medium">中</option>
            <option value="low">低</option>
          </select>
        </label>
        <label className="text-xs font-medium">
          负责人
          <input aria-label="整改任务负责人" className="mt-1 h-9 w-full rounded-md border border-border px-3 font-normal" value={ownerName} onChange={(event) => setOwnerName(event.target.value)} />
        </label>
        <label className="text-xs font-medium">
          截止日期
          <input aria-label="整改任务截止日期" className="mt-1 h-9 w-full rounded-md border border-border px-3 font-normal" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
        </label>
        <label className="text-xs font-medium sm:col-span-2">
          整改建议
          <textarea aria-label="整改建议" className="mt-1 min-h-20 w-full rounded-md border border-border px-3 py-2 font-normal" value={recommendationText} onChange={(event) => setRecommendationText(event.target.value)} />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" className="inline-flex h-9 items-center rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50" disabled={created || !title.trim() || !recommendationText.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
          创建整改任务
        </button>
        {created && <><span className="text-sm text-emerald-700">整改任务已创建</span><Link className="text-sm font-medium text-accent" href={`/reports/${reportId}/actions`}>查看整改任务</Link></>}
        {mutation.isError && <span className="text-sm text-red-600">整改任务创建失败，请重试。</span>}
      </div>
    </section>
  );
}
