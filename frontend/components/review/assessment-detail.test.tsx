import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
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
    system_rationale: "No evidence was found.",
    system_rationale_display: "未找到有效证据。",
    system_missing_items: ["substantive disclosure"],
    system_missing_items_display: ["实质披露内容"],
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
    latest_snapshot_id: "snapshot-1",
    latest_ai_suggestion: {
      suggestion_id: `suggestion-${assessmentId}`,
      assessment_id: assessmentId,
      run_id: "run-1",
      status: "succeeded",
      provider: "deepseek",
      model: "deepseek-v4-flash",
      prompt_version: "ai-assessment-v1",
      input_hash: "hash-1",
      suggested_verdict: "partially_disclosed",
      rationale_zh: "AI 建议补充核对披露范围。",
      missing_items_zh: ["披露范围"],
      evidence_ids: [],
      evidence_pdf_pages: [],
      confidence: 0.8,
      guardrail_codes: [],
      retry_count: 0,
    },
  };
}

describe("AssessmentDetail", () => {
  it("separates rule analysis, AI advice and the current human-reviewed result", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const reviewed = {
      ...detail("assessment-1", "GRI 2-5-a"),
      reviewed_verdict: "disclosed",
      effective_verdict: "disclosed",
      review_status: "reviewed_modified",
      rationale: "人工采纳的 AI 依据。",
      rationale_display: "人工采纳的 AI 依据。",
      missing_items: [],
      missing_items_display: [],
    } satisfies AssessmentDetailResponse;

    render(
      <QueryClientProvider client={queryClient}>
        <AssessmentDetail reportId="report-1" detail={reviewed} reviewerName="张三" onEvidencePage={() => undefined} />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "规则分析" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI 辅助建议" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "人工复核" })).toBeInTheDocument();
    expect(screen.getByText("规则结论：待确认")).toBeInTheDocument();
    const ruleAnalysis = screen.getByRole("region", { name: "规则分析" });
    expect(within(ruleAnalysis).getByText("未找到有效证据。")).toBeInTheDocument();
    expect(within(ruleAnalysis).getByText("实质披露内容")).toBeInTheDocument();
    expect(within(ruleAnalysis).queryByText("人工采纳的 AI 依据。")).not.toBeInTheDocument();
    expect(screen.getByText("AI 建议结论")).toBeInTheDocument();
    expect(screen.getByText("当前有效结论：已披露")).toBeInTheDocument();
    expect(screen.getByText("当前复核状态：已修改")).toBeInTheDocument();
    expect(screen.queryByText("AI最终结论")).not.toBeInTheDocument();
  });

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
