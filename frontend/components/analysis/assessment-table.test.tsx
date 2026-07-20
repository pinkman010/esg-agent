import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { AssessmentTable } from "./assessment-table";

describe("AssessmentTable", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows business labels for the complete assessment list", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const page = Number(new URL(String(input)).searchParams.get("page") ?? "1");
      const first = (page - 1) * 50 + 1;
      const body = {
        items: page <= 10 ? [{ assessment_id: `a-${first}`, requirement_id: `GRI 2-${first}-a`, requirement_name_zh: "组织法定名称", gri_topic: "GRI 2", system_verdict: "disclosed", reviewed_verdict: null, effective_verdict: "disclosed", risk_level: "low", review_priority: "low", evidence_status: "valid_direct", applicability_status: "applicable", risk_reason_codes: ["direct_disclosure_evidence"], review_status: "pending_review", evidence_count: 1, source_pdf_pages: [6], action_status: null }] : [],
        page,
        page_size: 50,
        total: 493,
      };
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<AssessmentTable reportId="report-1" />);
    expect(await screen.findByRole("link", { name: "GRI 2-1-a" })).toHaveAttribute(
      "href",
      "/reports/report-1/review?assessmentId=a-1",
    );
    expect(screen.getByText("已披露")).toBeInTheDocument();
    expect(screen.getByText("待复核")).toBeInTheDocument();
    expect(screen.queryByText("pending_review")).not.toBeInTheDocument();
    expect(screen.getByText("第 1–50 条，共 493 条")).toBeInTheDocument();
    expect(screen.getByText("共 493 个独立判断项；另有 78 个父级上下文项和 6 个方法待确认项，不生成独立披露结论。")).toBeInTheDocument();
    expect(screen.queryByText(/577 条结果/)).not.toBeInTheDocument();
    expect(screen.getByText("低优先级")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("GRI 2-51-a")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("page=2"), expect.anything());

    fireEvent.click(screen.getByRole("button", { name: "末页" }));
    expect(await screen.findByText("GRI 2-451-a")).toBeInTheDocument();
    expect(screen.getByText("第 451–493 条，共 493 条")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("page=10"), expect.anything());
  });
});
