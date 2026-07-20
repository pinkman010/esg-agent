import { describe, expect, it } from "vitest";

import {
  aiGuardrailLabel,
  aiStatusLabel,
  formatAIConfidence,
  isUsableAISuggestion,
} from "./ai-presentation";
import type { AIAssessmentSuggestion } from "./types";

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
    input_hash: "hash",
    suggested_verdict: "partially_disclosed",
    retry_count: 0,
    ...overrides,
  };
}

describe("AI presentation", () => {
  it("uses advisory Chinese status labels", () => {
    expect(aiStatusLabel("succeeded")).toBe("AI 建议已生成");
    expect(aiStatusLabel("failed")).toBe("AI 辅助未完成");
    expect(aiStatusLabel("skipped")).toBe("AI 辅助已跳过");
  });

  it("localizes known and unknown guardrails without exposing internal codes", () => {
    expect(aiGuardrailLabel("verdict_upgrade_requires_human_review")).toContain("不能直接升级");
    expect(aiGuardrailLabel("unexpected_internal_code")).toBe(
      "AI 建议触发安全校验，需要人工判断。",
    );
  });

  it("formats confidence as a bounded percentage", () => {
    expect(formatAIConfidence(0.723)).toBe("72%");
    expect(formatAIConfidence(2)).toBe("100%");
    expect(formatAIConfidence(-1)).toBe("0%");
    expect(formatAIConfidence(null)).toBe("未提供");
  });

  it("only treats successful suggestions with a verdict as usable", () => {
    expect(isUsableAISuggestion(suggestion())).toBe(true);
    expect(isUsableAISuggestion(suggestion({ status: "failed" }))).toBe(false);
    expect(isUsableAISuggestion(suggestion({ suggested_verdict: null }))).toBe(false);
    expect(isUsableAISuggestion(null)).toBe(false);
  });
});
