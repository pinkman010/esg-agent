import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { RiskQueue } from "./risk-queue";

describe("RiskQueue", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows high-risk requirements with Chinese business reasons", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{
        assessment_id: "assessment-1",
        requirement_id: "GRI 2-1-b",
        requirement_name_zh: "组织所有权与法律形式",
        gri_topic: "GRI 2",
        system_verdict: "unknown",
        reviewed_verdict: null,
        effective_verdict: "unknown",
        risk_level: "high",
        risk_reason_codes: ["unknown_verdict", "no_valid_evidence"],
        review_status: "needs_manual_review",
        evidence_count: 0,
        source_pdf_pages: [],
        action_status: null,
      }],
      page: 1,
      page_size: 50,
      total: 1,
    }), { status: 200, headers: { "content-type": "application/json" } })));

    renderWithQuery(<RiskQueue reportId="report-1" />);

    expect(await screen.findByText("GRI 2-1-b")).toBeInTheDocument();
    expect(screen.getByText("未找到有效证据")).toBeInTheDocument();
    expect(screen.queryByText("unknown_verdict")).not.toBeInTheDocument();
  });
});
