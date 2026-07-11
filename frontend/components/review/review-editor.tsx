"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Save } from "lucide-react";
import { useState } from "react";

import { saveReviewSnapshot } from "@/lib/api";

export function ReviewEditor({ assessmentId, reviewerName }: { assessmentId: string; reviewerName: string }) {
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const mutation = useMutation({
    mutationFn: ({ operation, reason }: { operation: "approve" | "modify"; reason: string }) => saveReviewSnapshot(assessmentId, {
      operation_type: operation,
      reviewer_name: reviewerName,
      reason_code: reason,
      reviewer_note: note,
      reviewed_verdict: null,
      evidence_pages: null,
      evidence_preview: null,
      rationale: null,
      missing_items: null,
      expected_previous_snapshot_id: null,
    }),
    onSuccess: () => setSaved(true),
  });

  return (
    <div className="border-t border-border pt-4">
      <label className="block text-sm font-medium">
        复核备注
        <textarea
          className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 font-normal"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="inline-flex h-9 items-center gap-2 rounded-md bg-accent px-3 text-sm font-medium text-accent-foreground"
          onClick={() => mutation.mutate({ operation: "approve", reason: "system_result_confirmed" })}
        >
          <Check aria-hidden="true" className="h-4 w-4" />
          快速通过
        </button>
        <button
          type="button"
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium disabled:opacity-50"
          disabled={!note.trim()}
          onClick={() => mutation.mutate({ operation: "modify", reason: "manual_correction" })}
        >
          <Save aria-hidden="true" className="h-4 w-4" />
          保存修改
        </button>
        {saved && <span className="self-center text-sm text-emerald-700">复核记录已保存</span>}
      </div>
    </div>
  );
}
