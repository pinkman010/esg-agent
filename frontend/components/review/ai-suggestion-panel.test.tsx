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

function renderPanel(
  value: AIAssessmentSuggestion | null,
  availability: "enabled" | "disabled" | "loading" | "unavailable" = "unavailable",
) {
  const callbacks = {
    onEvidencePage: vi.fn(),
    onAccept: vi.fn(),
    onEdit: vi.fn(),
    onReject: vi.fn(),
  };
  render(
    <AISuggestionPanel
      suggestion={value}
      availability={availability}
      busy={false}
      {...callbacks}
    />,
  );
  return callbacks;
}

describe("AISuggestionPanel", () => {
  it("explains that AI was not enabled for the run", () => {
    renderPanel(null, "disabled");

    expect(
      screen.getByText("本次分析未启用 AI 辅助，规则结果仍有效。"),
    ).toBeInTheDocument();
    expect(screen.getByText(/AI 建议仅供人工复核参考/)).toBeInTheDocument();
  });

  it("explains that an item has no suggestion in an AI-enabled run", () => {
    renderPanel(null, "enabled");

    expect(
      screen.getByText("本次已启用 AI 辅助，该项未进入候选范围或未生成逐项建议。"),
    ).toBeInTheDocument();
  });

  it("shows explicit loading and unavailable AI states", () => {
    renderPanel(null, "loading");

    expect(screen.getByText("正在读取本次 AI 辅助状态...")).toBeInTheDocument();

    renderPanel(null, "unavailable");
    expect(
      screen.getByText("暂无法确认本次 AI 辅助状态，规则结果仍有效。"),
    ).toBeInTheDocument();
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

  it("shows guardrail review without actionable or internal data", () => {
    renderPanel(suggestion({
      status: "failed",
      guardrail_codes: ["verdict_upgrade_requires_human_review"],
      error_message: "secret upstream exception",
    }));

    expect(
      screen.getByText("AI 建议触发安全校验，需人工独立判断"),
    ).toBeInTheDocument();
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
      guardrail_codes: ["low_review_priority"],
    }));

    expect(screen.getByText("该项未调用 AI")).toBeInTheDocument();
    expect(screen.getByText("该项复核优先级较低，本次未调用 AI。")).toBeInTheDocument();
    expect(
      screen.queryByText("AI 建议触发安全校验，需要人工判断。"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("AI 辅助未完成，规则结果仍有效")).not.toBeInTheDocument();
  });
});
