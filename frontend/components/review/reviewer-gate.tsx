"use client";

import { useState } from "react";
import { ReviewWorkspace } from "./review-workspace";

export function ReviewerGate({
  reportId,
  initialAssessmentId,
}: {
  reportId: string;
  initialAssessmentId?: string;
}) {
  const [name, setName] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  if (confirmed) {
    return (
      <ReviewWorkspace
        reportId={reportId}
        reviewerName={name}
        initialAssessmentId={initialAssessmentId}
      />
    );
  }

  return (
    <div className="mx-auto max-w-md px-6 py-12">
      <h1 className="text-xl font-semibold">填写复核人</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        复核记录将保存本次填写的复核人名称、时间和原因。每次进入均需重新填写。
      </p>
      <label className="mt-6 block text-sm font-medium">
        复核人名称
        <input
          className="mt-2 h-10 w-full rounded-md border border-border px-3 font-normal"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <button
        type="button"
        className="mt-4 h-10 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground disabled:opacity-50"
        disabled={!name.trim()}
        onClick={() => {
          setName(name.trim());
          setConfirmed(true);
        }}
      >
        进入复核工作台
      </button>
    </div>
  );
}
