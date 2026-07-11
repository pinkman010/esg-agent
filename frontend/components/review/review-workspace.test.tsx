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
      .mockResolvedValueOnce(response({ items: [{ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_name_zh: "组织法定名称", gri_topic: "GRI 2", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", risk_level: "high", risk_reason_codes: ["no_valid_evidence"], review_status: "pending_review", evidence_count: 1, source_pdf_pages: [6], action_status: null }], page: 1, page_size: 50, total: 1 }))
      .mockResolvedValueOnce(response({ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_text: "report its legal name", system_verdict: "unknown", reviewed_verdict: null, effective_verdict: "unknown", review_status: "pending_review", risk_level: "high", risk_reason_codes: ["no_valid_evidence"], rationale: "待核实", missing_items: ["法定名称"], evidence_items: [{ evidence_id: "e-1", source_pdf_page: 6, source_report_page: 5, page_label: "PDF 第 6 页 / 报告页 5", evidence_preview: "公司法定名称", source_method: "pdfplumber", quality_flags: [], bbox: null }], latest_snapshot_id: null })));

    renderWithQuery(<ReviewWorkspace reportId="report-1" reviewerName="张三" />);
    fireEvent.click(await screen.findByText("GRI 2-1-a"));

    expect(await screen.findByText("判断依据")).toBeInTheDocument();
    expect(screen.getByTitle("PDF 证据")).toHaveAttribute("src", expect.stringContaining("#page=6"));
  });
});
