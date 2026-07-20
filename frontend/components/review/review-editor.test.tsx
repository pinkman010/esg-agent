import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AIAssessmentSuggestion, AssessmentDetailResponse } from "@/lib/types";
import { renderWithQuery } from "@/tests/render-with-query";
import { ReviewEditor } from "./review-editor";

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
  rationale_zh: "AI 判断依据",
  missing_items_zh: ["AI 缺失项"],
  evidence_ids: ["evidence-2"],
  evidence_pdf_pages: [67],
  confidence: 0.8,
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
  system_rationale: "Rule rationale.",
  system_rationale_display: "规则判断依据。",
  system_missing_items: ["rule missing item"],
  system_missing_items_display: ["规则缺失项"],
  reviewed_verdict: null,
  effective_verdict: "unknown",
  review_status: "pending_review",
  risk_level: "high",
  review_priority: "high",
  evidence_status: "missing",
  applicability_status: "applicable",
  risk_reason_codes: ["no_valid_evidence"],
  rationale: "Rule rationale.",
  rationale_display: "规则判断依据。",
  missing_items: ["rule missing item"],
  missing_items_display: ["规则缺失项"],
  evidence_items: [{
    evidence_id: "evidence-1",
    source_pdf_page: 41,
    source_report_page: 39,
    page_label: "39",
    evidence_preview: "rule evidence",
    source_method: "text",
    quality_flags: [],
    bbox: null,
  }],
  latest_snapshot_id: "snapshot-2",
  latest_ai_suggestion: suggestion,
};

function okResponse() {
  return new Response(JSON.stringify({ snapshot_id: "snapshot-3" }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function renderEditor() {
  return renderWithQuery(
    <ReviewEditor detail={detail} reviewerName="张三" onEvidencePage={() => undefined} />,
  );
}

function requestBody(fetchMock: ReturnType<typeof vi.fn>) {
  return JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
}

describe("ReviewEditor", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("quick-approves the current result against the latest snapshot", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderEditor();

    fireEvent.click(screen.getByRole("button", { name: "快速通过规则结论" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock)).toMatchObject({
      operation_type: "approve",
      reviewer_name: "张三",
      reason_code: "system_result_confirmed",
      expected_previous_snapshot_id: "snapshot-2",
    });
    expect(await screen.findByText("复核记录已保存")).toBeInTheDocument();
  });

  it("records an independent applicability decision", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderEditor();

    fireEvent.change(screen.getByLabelText("复核备注"), { target: { value: "确认该要求适用" } });
    fireEvent.click(screen.getByRole("button", { name: "确认适用" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock)).toMatchObject({
      operation_type: "modify",
      reason_code: "applicability_reviewed",
      reviewed_applicability_status: "applicable",
      expected_previous_snapshot_id: "snapshot-2",
    });
  });

  it("accepts an AI suggestion with auditable provenance", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderEditor();

    fireEvent.click(screen.getByRole("button", { name: "采纳 AI 建议" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock)).toMatchObject({
      reason_code: "ai_suggestion_accepted",
      reviewer_note: expect.stringContaining("suggestion-1"),
      reviewed_verdict: "partially_disclosed",
      rationale: "AI 判断依据",
      missing_items: ["AI 缺失项"],
      evidence_pages: [67],
      expected_previous_snapshot_id: "snapshot-2",
    });
  });

  it("loads an AI suggestion for human editing without saving immediately", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderEditor();

    fireEvent.click(screen.getByRole("button", { name: "载入 AI 建议并修改" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByLabelText("人工结论")).toHaveValue("partially_disclosed");
    expect(screen.getByLabelText("人工判断依据")).toHaveValue("AI 判断依据");
    expect(screen.getByLabelText("PDF 证据页")).toHaveValue("67");

    fireEvent.change(screen.getByLabelText("人工结论"), { target: { value: "disclosed" } });
    fireEvent.change(screen.getByLabelText("复核备注"), { target: { value: "人工核对后调整" } });
    fireEvent.click(screen.getByRole("button", { name: "保存人工修改" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock)).toMatchObject({
      reason_code: "ai_suggestion_modified",
      reviewer_note: expect.stringMatching(/人工核对后调整.*suggestion-1/),
      reviewed_verdict: "disclosed",
    });
  });

  it("rejects an AI suggestion and persists the rule result", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderEditor();

    fireEvent.click(screen.getByRole("button", { name: "拒绝 AI 建议并保留规则结论" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock)).toMatchObject({
      reason_code: "ai_suggestion_rejected",
      reviewer_note: expect.stringContaining("suggestion-1"),
      reviewed_verdict: "unknown",
      rationale: "Rule rationale.",
      missing_items: ["rule missing item"],
      evidence_pages: [41],
    });
  });

  it("does not send an invalid evidence page list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderEditor();

    fireEvent.change(screen.getByLabelText("PDF 证据页"), { target: { value: "41, abc" } });
    fireEvent.change(screen.getByLabelText("复核备注"), { target: { value: "人工修改" } });
    fireEvent.click(screen.getByRole("button", { name: "保存人工修改" }));

    expect(await screen.findByText("证据页码必须是正整数")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [409, "该核查项已被其他复核操作更新，请刷新后重试。"],
    [422, "复核内容不完整，请检查备注和修改字段。"],
  ])("shows the actionable message for API status %s", async (status, expectedMessage) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "error" }), {
      status,
      headers: { "content-type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    renderEditor();

    fireEvent.click(screen.getByRole("button", { name: "快速通过规则结论" }));

    expect(await screen.findByText(expectedMessage)).toBeInTheDocument();
  });
});
