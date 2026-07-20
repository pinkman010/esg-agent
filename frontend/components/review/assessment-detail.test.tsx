import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AssessmentDetailResponse } from "@/lib/types";
import { AssessmentDetail } from "./assessment-detail";

function detail(assessmentId: string, requirementId: string): AssessmentDetailResponse {
  return {
    assessment_id: assessmentId,
    requirement_id: requirementId,
    requirement_text: `${requirementId} requirement`,
    source_requirement_text: `${requirementId} source requirement`,
    effective_requirement_text: `${requirementId} requirement`,
    context_requirement_ids: [],
    structure_status: "verified",
    system_verdict: "unknown",
    reviewed_verdict: null,
    effective_verdict: "unknown",
    review_status: "pending_review",
    risk_level: "high",
    review_priority: "high",
    evidence_status: "missing",
    applicability_status: "applicable",
    risk_reason_codes: ["no_valid_evidence"],
    rationale: "No evidence was found.",
    rationale_display: "未找到有效证据。",
    missing_items: ["substantive disclosure"],
    missing_items_display: ["实质披露内容"],
    evidence_items: [],
    latest_snapshot_id: null,
  };
}

describe("AssessmentDetail", () => {
  it("resets review and action form state when switching requirements", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const first = detail("assessment-1", "GRI 2-5-a");
    const second = detail("assessment-2", "GRI 2-6-a");
    const view = render(
      <QueryClientProvider client={queryClient}>
        <AssessmentDetail reportId="report-1" detail={first} reviewerName="张三" onEvidencePage={() => undefined} />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("复核备注"), { target: { value: "上一条复核备注" } });
    fireEvent.change(screen.getByLabelText("任务标题"), { target: { value: "上一条整改任务" } });

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <AssessmentDetail reportId="report-1" detail={second} reviewerName="张三" onEvidencePage={() => undefined} />
      </QueryClientProvider>,
    );

    expect(screen.getByLabelText("复核备注")).toHaveValue("");
    expect(screen.getByLabelText("任务标题")).toHaveValue("补充 GRI 2-6-a 披露缺口");
  });
});
