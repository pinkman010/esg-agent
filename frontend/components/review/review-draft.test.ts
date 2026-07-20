import { describe, expect, it } from "vitest";

import type { AIAssessmentSuggestion, AssessmentDetailResponse } from "@/lib/types";
import {
  buildAcceptAIPayload,
  buildManualModifyPayload,
  buildRejectAIPayload,
  draftFromAISuggestion,
  draftFromDetail,
  parseEvidencePages,
} from "./review-draft";

const suggestion: AIAssessmentSuggestion = {
  suggestion_id: "suggestion-1",
  assessment_id: "assessment-1",
  run_id: "run-1",
  status: "succeeded",
  provider: "deepseek",
  model: "deepseek-v4-flash",
  prompt_version: "ai-assessment-v1",
  input_hash: "hash-1",
  suggested_verdict: "partially_disclosed",
  rationale_zh: "报告披露了部分要求，但缺少范围说明。",
  missing_items_zh: ["披露范围"],
  evidence_ids: ["evidence-2"],
  evidence_pdf_pages: [67],
  confidence: 0.83,
  guardrail_codes: [],
  retry_count: 0,
};

const detail: AssessmentDetailResponse = {
  assessment_id: "assessment-1",
  requirement_id: "GRI 403-9-e",
  requirement_text: "requirement",
  source_requirement_text: "source requirement",
  effective_requirement_text: "effective requirement",
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
  rationale: "No valid evidence was found.",
  rationale_display: "未找到有效证据。",
  missing_items: ["substantive disclosure"],
  missing_items_display: ["实质披露内容"],
  evidence_items: [
    {
      evidence_id: "evidence-1",
      source_pdf_page: 41,
      source_report_page: 39,
      page_label: "39",
      evidence_preview: "rule evidence one",
      source_method: "toc",
      quality_flags: [],
      bbox: null,
    },
    {
      evidence_id: "evidence-2",
      source_pdf_page: 67,
      source_report_page: 65,
      page_label: "65",
      evidence_preview: "rule evidence two",
      source_method: "text",
      quality_flags: [],
      bbox: null,
    },
  ],
  latest_snapshot_id: "snapshot-2",
  latest_ai_suggestion: suggestion,
};

describe("review draft", () => {
  it("creates an editable draft from the current rule or reviewed result", () => {
    expect(draftFromDetail(detail)).toEqual({
      verdict: "unknown",
      rationale: "未找到有效证据。",
      missingItemsText: "实质披露内容",
      evidencePagesText: "41, 67",
      note: "",
      sourceSuggestionId: null,
    });
  });

  it("loads guarded AI fields into an unsaved human draft", () => {
    expect(draftFromAISuggestion(detail, suggestion)).toEqual({
      verdict: "partially_disclosed",
      rationale: "报告披露了部分要求，但缺少范围说明。",
      missingItemsText: "披露范围",
      evidencePagesText: "67",
      note: "",
      sourceSuggestionId: "suggestion-1",
    });
  });

  it("builds an auditable AI acceptance payload", () => {
    expect(buildAcceptAIPayload(detail, suggestion, "张三")).toMatchObject({
      operation_type: "modify",
      reviewer_name: "张三",
      reason_code: "ai_suggestion_accepted",
      reviewer_note: expect.stringContaining("suggestion-1"),
      reviewed_verdict: "partially_disclosed",
      rationale: "报告披露了部分要求，但缺少范围说明。",
      missing_items: ["披露范围"],
      evidence_pages: [67],
      expected_previous_snapshot_id: "snapshot-2",
    });
  });

  it("builds an auditable AI rejection payload from rule fields", () => {
    expect(buildRejectAIPayload(detail, suggestion, "张三")).toMatchObject({
      operation_type: "modify",
      reviewer_name: "张三",
      reason_code: "ai_suggestion_rejected",
      reviewer_note: expect.stringContaining("suggestion-1"),
      reviewed_verdict: "unknown",
      rationale: "No valid evidence was found.",
      missing_items: ["substantive disclosure"],
      evidence_pages: [41, 67],
      expected_previous_snapshot_id: "snapshot-2",
    });
  });

  it("marks an edited AI draft as a human modification and retains provenance", () => {
    const draft = {
      ...draftFromAISuggestion(detail, suggestion),
      verdict: "disclosed" as const,
      note: "人工核对后调整结论",
    };

    expect(buildManualModifyPayload(detail, draft, "张三")).toMatchObject({
      reason_code: "ai_suggestion_modified",
      reviewer_note: expect.stringMatching(/人工核对后调整结论.*suggestion-1/),
      reviewed_verdict: "disclosed",
      expected_previous_snapshot_id: "snapshot-2",
    });
  });

  it("validates, deduplicates and sorts PDF evidence pages", () => {
    expect(parseEvidencePages("67, 41, 67")).toEqual([41, 67]);
    expect(() => parseEvidencePages("41, abc")).toThrow("证据页码必须是正整数");
    expect(() => parseEvidencePages("0")).toThrow("证据页码必须是正整数");
  });
});
