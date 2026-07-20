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
      .mockResolvedValueOnce(response({ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_text: "report its legal name", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", review_status: "pending_review", risk_level: "high", review_priority: "high", evidence_status: "conflict", applicability_status: "applicable", risk_reason_codes: ["sufficiency_conflict"], rationale: "The report index contains an omission note.", rationale_display: "报告 GRI 内容索引包含从略说明。", missing_items: ["source basis"], missing_items_display: ["数据来源依据"], evidence_items: [{ evidence_id: "e-1", source_pdf_page: 6, source_report_page: 5, page_label: "PDF 第 6 页 / 报告页 5", evidence_preview: "公司法定名称", source_method: "pdfplumber", quality_flags: [], bbox: null }], latest_snapshot_id: null })));

    renderWithQuery(<ReviewWorkspace reportId="report-1" reviewerName="张三" />);
    expect(screen.queryByTitle("PDF 证据")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByText("GRI 2-1-a"));

    expect(await screen.findByText("判断依据")).toBeInTheDocument();
    expect(screen.getByText("报告 GRI 内容索引包含从略说明。")).toBeInTheDocument();
    expect(screen.queryByText("The report index contains an omission note.")).not.toBeInTheDocument();
    expect(screen.getByText("证据状态")).toBeInTheDocument();
    expect(screen.getByText("存在冲突")).toBeInTheDocument();
    expect(screen.getByText("适用性状态")).toBeInTheDocument();
    expect(screen.getByText("适用")).toBeInTheDocument();
    expect(screen.getByText("复核优先级")).toBeInTheDocument();
    expect(screen.getAllByText("高优先级")).toHaveLength(2);
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=6"));
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
      .mockResolvedValueOnce(response({ items: [{ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_name_zh: "组织法定名称", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "high", risk_reason_codes: ["no_valid_evidence"], review_status: "pending_review", evidence_count: 0, source_pdf_pages: [], action_status: null }], page: 1, page_size: 50, total: 1 }))
      .mockImplementationOnce(() => detailPromise));

    renderWithQuery(<ReviewWorkspace reportId="report-1" reviewerName="张三" />);
    fireEvent.click(await screen.findByText("GRI 2-1-a"));

    expect(await screen.findByText("正在加载核查详情...")).toBeInTheDocument();
    rejectDetail?.(new Error("network failed"));
    expect(await screen.findByText("核查详情加载失败，请重新选择或稍后重试。")).toBeInTheDocument();
    expect(screen.queryByTitle("PDF 证据")).not.toBeInTheDocument();
  });
});
