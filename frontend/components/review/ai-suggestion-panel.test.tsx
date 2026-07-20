import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AIAssessmentSuggestion } from "@/lib/types";
import { AISuggestionPanel } from "./ai-suggestion-panel";

function suggestion(
  overrides: Partial<AIAssessmentSuggestion> = {},
): AIAssessmentSuggestion {
  return {
    suggestion_id: "ai-suggestion-1",
    assessment_id: "assessment-1",
    run_id: "run-1",
    status: "succeeded",
    provider: "deepseek",
    model: "deepseek-v4-flash",
    prompt_version: "deepseek-gri-assist-v1.2",
    input_hash: "private-input-hash",
    suggested_verdict: "partially_disclosed",
    rationale_zh: "报告披露了部分相关数据。",
    missing_items_zh: ["缺少计算边界"],
    evidence_ids: ["evidence-1"],
    evidence_pdf_pages: [41],
    confidence: 0.82,
    guardrail_codes: [],
    usage: { total_tokens: 999 },
    retry_count: 0,
    raw_response: { secret: "raw model response" },
    ...overrides,
  };
}

function renderPanel(value: AIAssessmentSuggestion | null) {
  const callbacks = {
    onEvidencePage: vi.fn(),
    onAccept: vi.fn(),
    onEdit: vi.fn(),
    onReject: vi.fn(),
  };
  render(<AISuggestionPanel suggestion={value} busy={false} {...callbacks} />);
  return callbacks;
}

describe("AISuggestionPanel", () => {
  it("shows a neutral empty state when no suggestion exists", () => {
    renderPanel(null);

    expect(screen.getByText("该核查项暂无 AI 建议")).toBeInTheDocument();
    expect(screen.getByText(/AI 建议仅供人工复核参考/)).toBeInTheDocument();
  });

  it("shows a successful advisory suggestion and connects all actions", () => {
    const callbacks = renderPanel(suggestion());

    expect(screen.getByText("AI 建议已生成")).toBeInTheDocument();
    expect(screen.getByText("部分披露")).toBeInTheDocument();
    expect(screen.getByText("报告披露了部分相关数据。")).toBeInTheDocument();
    expect(screen.getByText("缺少计算边界")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText(/deepseek-v4-flash/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看 AI 证据 PDF 第 41 页" }));
    fireEvent.click(screen.getByRole("button", { name: "采纳 AI 建议" }));
    fireEvent.click(screen.getByRole("button", { name: "载入 AI 建议并修改" }));
    fireEvent.click(screen.getByRole("button", { name: "拒绝 AI 建议并保留规则结论" }));

    expect(callbacks.onEvidencePage).toHaveBeenCalledWith(41);
    expect(callbacks.onAccept).toHaveBeenCalledOnce();
    expect(callbacks.onEdit).toHaveBeenCalledOnce();
    expect(callbacks.onReject).toHaveBeenCalledOnce();
  });

  it("shows safe failure and guardrail messages without actionable or internal data", () => {
    renderPanel(suggestion({
      status: "failed",
      guardrail_codes: ["verdict_upgrade_requires_human_review"],
      error_message: "secret upstream exception",
    }));

    expect(screen.getByText("AI 辅助未完成，规则结果仍有效")).toBeInTheDocument();
    expect(screen.getByText(/不能直接升级规则结论/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "采纳 AI 建议" })).not.toBeInTheDocument();
    expect(screen.queryByText("secret upstream exception")).not.toBeInTheDocument();
    expect(screen.queryByText("private-input-hash")).not.toBeInTheDocument();
    expect(screen.queryByText("raw model response")).not.toBeInTheDocument();
    expect(screen.queryByText("999")).not.toBeInTheDocument();
  });

  it("explains skipped suggestions without presenting them as failures", () => {
    renderPanel(suggestion({
      status: "skipped",
      suggested_verdict: null,
      guardrail_codes: ["call_budget_exhausted"],
    }));

    expect(screen.getByText("AI 辅助已跳过")).toBeInTheDocument();
    expect(screen.getByText("本次 AI 调用已达到数量上限。")).toBeInTheDocument();
    expect(screen.queryByText("AI 辅助未完成，规则结果仍有效")).not.toBeInTheDocument();
  });
});
