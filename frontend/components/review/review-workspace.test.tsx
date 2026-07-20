import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReviewWorkspace } from "./review-workspace";

function response(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

describe("ReviewWorkspace", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("connects the risk queue, requirement detail, and PDF evidence columns", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(response({ items: [{ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_name_zh: "组织法定名称", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "high", review_priority: "high", evidence_status: "conflict", applicability_status: "applicable", risk_reason_codes: ["sufficiency_conflict"], review_status: "pending_review", evidence_count: 1, source_pdf_pages: [6], action_status: null }], page: 1, page_size: 50, total: 1 }))
      .mockResolvedValueOnce(response({ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_text: "report its legal name", source_requirement_text: "source", effective_requirement_text: "effective", context_requirement_ids: [], structure_status: "verified", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", review_status: "pending_review", risk_level: "high", review_priority: "high", evidence_status: "conflict", applicability_status: "applicable", risk_reason_codes: ["sufficiency_conflict"], rationale: "The report index contains an omission note.", rationale_display: "报告 GRI 内容索引包含从略说明。", missing_items: ["source basis"], missing_items_display: ["数据来源依据"], evidence_items: [{ evidence_id: "e-1", source_pdf_page: 6, source_report_page: 5, page_label: "PDF 第 6 页 / 报告页 5", evidence_preview: "公司法定名称", source_method: "pdfplumber", quality_flags: [], bbox: null }], latest_snapshot_id: null, latest_ai_suggestion: { suggestion_id: "s-1", assessment_id: "a-1", run_id: "run-1", status: "succeeded", provider: "deepseek", model: "deepseek-v4-flash", prompt_version: "ai-assessment-v1", input_hash: "hash-1", suggested_verdict: "disclosed", rationale_zh: "AI 识别到直接证据。", missing_items_zh: [], evidence_ids: ["e-1"], evidence_pdf_pages: [67], confidence: 0.9, guardrail_codes: [], retry_count: 0 } })));

    renderWithQuery(<ReviewWorkspace reportId="report-1" reviewerName="张三" />);
    expect(screen.queryByTitle("PDF 证据")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByText("GRI 2-1-a"));

    expect(await screen.findByText("判断依据")).toBeInTheDocument();
    expect(screen.getAllByText("报告 GRI 内容索引包含从略说明。")).toHaveLength(2);
    expect(screen.queryByText("The report index contains an omission note.")).not.toBeInTheDocument();
    expect(screen.getByText("证据状态")).toBeInTheDocument();
    expect(screen.getByText("存在冲突")).toBeInTheDocument();
    expect(screen.getByText("适用性状态")).toBeInTheDocument();
    expect(screen.getByText("适用")).toBeInTheDocument();
    expect(screen.getByText("复核优先级")).toBeInTheDocument();
    expect(screen.getAllByText("高优先级")).toHaveLength(2);
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=6"));
    const aiEvidenceButton = screen.getByRole("button", { name: "查看 AI 证据 PDF 第 67 页" });
    expect(aiEvidenceButton).not.toHaveAttribute("download");
    fireEvent.click(aiEvidenceButton);
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=67"));
    fireEvent.click(screen.getByRole("button", { name: /PDF 第 6 页 \/ 报告页 5/ }));
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=6"));
  });

  it("resets the human draft and PDF while switching assessments", async () => {
    const queue = {
      items: [
        { assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_name_zh: "第一项", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "high", review_priority: "high", evidence_status: "missing", applicability_status: "applicable", risk_reason_codes: ["no_valid_evidence"], review_status: "pending_review", evidence_count: 1, source_pdf_pages: [6], action_status: null },
        { assessment_id: "a-2", requirement_id: "GRI 2-2-a", requirement_name_zh: "第二项", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "high", review_priority: "high", evidence_status: "missing", applicability_status: "applicable", risk_reason_codes: ["no_valid_evidence"], review_status: "pending_review", evidence_count: 1, source_pdf_pages: [8], action_status: null },
      ],
      page: 1,
      page_size: 50,
      total: 2,
    };
    const makeDetail = (assessmentId: string, requirementId: string, rulePage: number, aiPage: number) => ({
      assessment_id: assessmentId,
      requirement_id: requirementId,
      requirement_text: "requirement",
      source_requirement_text: "source",
      effective_requirement_text: "effective",
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
      rationale: "No evidence.",
      rationale_display: "未找到有效证据。",
      missing_items: ["item"],
      missing_items_display: ["缺失项"],
      evidence_items: [{ evidence_id: `e-${assessmentId}`, source_pdf_page: rulePage, source_report_page: rulePage - 1, page_label: `PDF 第 ${rulePage} 页`, evidence_preview: "evidence", source_method: "text", quality_flags: [], bbox: null }],
      latest_snapshot_id: null,
      latest_ai_suggestion: { suggestion_id: `s-${assessmentId}`, assessment_id: assessmentId, run_id: "run-1", status: "succeeded", provider: "deepseek", model: "deepseek-v4-flash", prompt_version: "ai-assessment-v1", input_hash: `hash-${assessmentId}`, suggested_verdict: "unknown", rationale_zh: "AI 建议人工核对。", missing_items_zh: ["缺失项"], evidence_ids: [], evidence_pdf_pages: [aiPage], confidence: 0.6, guardrail_codes: [], retry_count: 0 },
    });
    vi.stubGlobal("fetch", vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/assessments/a-1")) return Promise.resolve(response(makeDetail("a-1", "GRI 2-1-a", 6, 67)));
      if (url.includes("/assessments/a-2")) return Promise.resolve(response(makeDetail("a-2", "GRI 2-2-a", 8, 70)));
      return Promise.resolve(response(queue));
    }));

    renderWithQuery(<ReviewWorkspace reportId="report-1" reviewerName="张三" />);
    fireEvent.click(await screen.findByText("GRI 2-1-a"));
    expect(await screen.findByRole("heading", { name: "GRI 2-1-a" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("复核备注"), { target: { value: "未保存的第一项备注" } });
    fireEvent.click(screen.getByRole("button", { name: "查看 AI 证据 PDF 第 67 页" }));
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=67"));

    fireEvent.click(screen.getByText("GRI 2-2-a"));
    expect(await screen.findByRole("heading", { name: "GRI 2-2-a" })).toBeInTheDocument();
    expect(screen.getByLabelText("复核备注")).toHaveValue("");
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=8"));
    fireEvent.click(screen.getByRole("button", { name: "查看 AI 证据 PDF 第 70 页" }));
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=70"));
  });

  it("switches to the independent applicability queue", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("applicability-queue")) {
        return Promise.resolve(response({ items: [{ assessment_id: "a-2", requirement_id: "GRI 2-2-a", requirement_name_zh: "适用性待确认", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "low", review_priority: "low", evidence_status: "missing", applicability_status: "undetermined", risk_reason_codes: ["unknown_verdict"], review_status: "pending_review", evidence_count: 0, source_pdf_pages: [], action_status: null }], page: 1, page_size: 50, total: 343 }));
      }
      return Promise.resolve(response({ items: [], page: 1, page_size: 50, total: 0 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ReviewWorkspace reportId="report-1" reviewerName="张三" />);
    fireEvent.click(screen.getByRole("button", { name: "适用性待判定" }));

    expect(await screen.findByText("GRI 2-2-a")).toBeInTheDocument();
    expect(screen.getByText("第 1–50 条，共 343 条")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("applicability-queue"), expect.anything());
  });

  it("shows detail loading and error states after selecting a queue item", async () => {
    let rejectDetail: ((reason?: unknown) => void) | undefined;
    const detailPromise = new Promise<Response>((_, reject) => { rejectDetail = reject; });
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(response({ items: [
        { assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_name_zh: "组织法定名称", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "high", review_priority: "high", evidence_status: "missing", applicability_status: "applicable", risk_reason_codes: ["no_valid_evidence"], review_status: "pending_review", evidence_count: 1, source_pdf_pages: [6], action_status: null },
        { assessment_id: "a-2", requirement_id: "GRI 2-2-a", requirement_name_zh: "员工信息", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "high", review_priority: "high", evidence_status: "missing", applicability_status: "applicable", risk_reason_codes: ["no_valid_evidence"], review_status: "pending_review", evidence_count: 0, source_pdf_pages: [], action_status: null },
      ], page: 1, page_size: 50, total: 2 }))
      .mockResolvedValueOnce(response({ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_text: "requirement", source_requirement_text: "source", effective_requirement_text: "effective", context_requirement_ids: [], structure_status: "verified", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", review_status: "pending_review", risk_level: "high", review_priority: "high", evidence_status: "missing", applicability_status: "applicable", risk_reason_codes: ["no_valid_evidence"], rationale: "No evidence.", rationale_display: "未找到有效证据。", missing_items: [], missing_items_display: [], evidence_items: [{ evidence_id: "e-1", source_pdf_page: 6, source_report_page: 5, page_label: "PDF 第 6 页", evidence_preview: "evidence", source_method: "text", quality_flags: [], bbox: null }], latest_snapshot_id: null, latest_ai_suggestion: null }))
      .mockImplementationOnce(() => detailPromise));

    renderWithQuery(<ReviewWorkspace reportId="report-1" reviewerName="张三" />);
    fireEvent.click(await screen.findByText("GRI 2-1-a"));
    expect(await screen.findByRole("heading", { name: "GRI 2-1-a" })).toBeInTheDocument();
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=6"));
    fireEvent.click(screen.getByText("GRI 2-2-a"));

    expect(await screen.findByText("正在加载核查详情...")).toBeInTheDocument();
    expect(screen.queryByTitle("PDF 证据")).not.toBeInTheDocument();
    rejectDetail?.(new Error("network failed"));
    expect(await screen.findByText("核查详情加载失败，请重新选择或稍后重试。")).toBeInTheDocument();
    expect(screen.queryByTitle("PDF 证据")).not.toBeInTheDocument();
  });
});
