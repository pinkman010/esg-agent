import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { AssessmentTable } from "./assessment-table";

describe("AssessmentTable", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows all 577 scope units while only assessed units link to review", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const page = Number(new URL(String(input)).searchParams.get("page") ?? "1");
      const first = (page - 1) * 50 + 1;
      const body = {
        items: page <= 12 ? [
          {
            requirement_id: `GRI 2-${first}-a`,
            gri_topic: "GRI 2",
            unit_status: "assessed",
            source_requirement_text: "组织法定名称",
            effective_requirement_text: "组织法定名称",
            component_requirement_ids: [],
            incorporated_into_requirement_ids: [],
            assessment_id: `a-${first}`,
            effective_verdict: "disclosed",
            review_priority: "low",
            review_status: "pending_review",
            source_pdf_pages: [6],
          },
          ...(page === 1 ? [{
            requirement_id: "GRI 2-1",
            gri_topic: "GRI 2",
            unit_status: "context_incorporated",
            source_requirement_text: "披露组织详细信息",
            effective_requirement_text: "披露组织详细信息",
            component_requirement_ids: [],
            incorporated_into_requirement_ids: ["GRI 2-1-a"],
            assessment_id: null,
            effective_verdict: null,
            review_priority: null,
            review_status: null,
            source_pdf_pages: [],
          }] : []),
        ] : [],
        page,
        page_size: 50,
        total: 577,
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
    expect(screen.getByText("完整 GRI 核查范围")).toBeInTheDocument();
    expect(screen.getByText("共 577 项")).toBeInTheDocument();
    expect(screen.getByText("第 1–50 项，共 577 项")).toBeInTheDocument();
    expect(screen.getByText("低优先级")).toBeInTheDocument();
    expect(screen.getByText("已纳入相关判断")).toBeInTheDocument();
    expect(screen.getByText("GRI 2-1")).not.toHaveAttribute("href");
    expect(screen.queryByText(/493|499|78|6 个方法待确认/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("GRI 2-51-a")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("page=2"), expect.anything());

    fireEvent.click(screen.getByRole("button", { name: "末页" }));
    expect(await screen.findByText("GRI 2-551-a")).toBeInTheDocument();
    expect(screen.getByText("第 551–577 项，共 577 项")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("page=12"), expect.anything());
  });

  it("shows a clear API error instead of an empty table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failed")));

    renderWithQuery(<AssessmentTable reportId="report-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("完整 GRI 核查范围加载失败");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows a clear empty state when the report has no scope items", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [],
      page: 1,
      page_size: 50,
      total: 0,
    }), { status: 200, headers: { "content-type": "application/json" } })));

    renderWithQuery(<AssessmentTable reportId="report-1" />);

    expect(await screen.findByText("当前报告暂无 GRI 核查范围")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
