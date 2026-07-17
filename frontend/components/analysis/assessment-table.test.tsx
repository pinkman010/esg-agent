import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { AssessmentTable } from "./assessment-table";

describe("AssessmentTable", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows business labels for the complete assessment list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [{ assessment_id: "a-1", requirement_id: "GRI 2-1-a", requirement_name_zh: "组织法定名称", gri_topic: "GRI 2", system_verdict: "disclosed", reviewed_verdict: null, effective_verdict: "disclosed", risk_level: "low", risk_reason_codes: ["direct_disclosure_evidence"], review_status: "pending_review", evidence_count: 1, source_pdf_pages: [6], action_status: null }], page: 1, page_size: 50, total: 577 }), { status: 200, headers: { "content-type": "application/json" } })));
    renderWithQuery(<AssessmentTable reportId="report-1" />);
    expect(await screen.findByText("GRI 2-1-a")).toBeInTheDocument();
    expect(screen.getByText("已披露")).toBeInTheDocument();
    expect(screen.getByText("待复核")).toBeInTheDocument();
    expect(screen.queryByText("pending_review")).not.toBeInTheDocument();
    expect(screen.getByText("共 577 条")).toBeInTheDocument();
  });
});
