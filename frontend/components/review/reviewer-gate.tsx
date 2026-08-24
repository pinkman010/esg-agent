"use client";

import { useState } from "react";
import { ReportPageHero } from "@/components/layout/report-page-hero";
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

  return (
    <div>
      <div className="mx-auto w-full max-w-7xl px-5 py-6 lg:px-7">
        <ReportPageHero
          eyebrow="人工判断层"
          title="人工复核"
          description="逐项核对规则结果、证据和 AI 辅助建议，最终有效结论以人工复核快照为准。"
          imageSrc="/visuals/module-materiality-benchmark.webp"
          imagePosition="52% 50%"
        />
      </div>
      {confirmed ? (
        <ReviewWorkspace
          reportId={reportId}
          reviewerName={name}
          initialAssessmentId={initialAssessmentId}
        />
      ) : (
        <div className="mx-auto max-w-md px-6 pb-12">
          <h2 className="text-xl font-semibold">填写复核人</h2>
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
      )}
    </div>
  );
}
