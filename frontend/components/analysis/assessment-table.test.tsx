import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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
    const assessmentLink = await screen.findByRole("link", { name: "GRI 2-1-a" });
    expect(assessmentLink).toHaveAttribute(
      "href",
      "/reports/report-1/review?assessmentId=a-1",
    );
    const assessmentRow = assessmentLink.closest("tr");
    expect(assessmentRow).not.toBeNull();
    expect(within(assessmentRow!).getByText("已披露")).toBeInTheDocument();
    expect(within(assessmentRow!).getByText("待复核")).toBeInTheDocument();
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

  it("applies search and all scope filters while resetting pagination", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = new URL(String(input));
      const body = {
        items: [{
          requirement_id: "GRI 2-1-a",
          gri_topic: "GRI 2",
          unit_status: "assessed",
          source_requirement_text: "report its legal name",
          effective_requirement_text: "披露组织法定名称",
          component_requirement_ids: [],
          incorporated_into_requirement_ids: [],
          assessment_id: "a-1",
          effective_verdict: "unknown",
          review_priority: "high",
          review_status: "pending_review",
          applicability_status: "undetermined",
          source_pdf_pages: [],
        }],
        page: Number(url.searchParams.get("page") ?? "1"),
        page_size: 50,
        total: 577,
      };
      return Promise.resolve(new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<AssessmentTable reportId="report-1" />);
    await screen.findByRole("link", { name: "GRI 2-1-a" });

    expect(Array.from((screen.getByLabelText("当前结论") as HTMLSelectElement).options).map((option) => option.value)).toEqual([
      "",
      "disclosed",
      "partially_disclosed",
      "not_disclosed",
      "unknown",
    ]);
    expect(Array.from((screen.getByLabelText("适用性") as HTMLSelectElement).options).map((option) => option.value)).toEqual([
      "",
      "applicable",
      "not_applicable_claimed",
      "not_applicable_confirmed",
      "undetermined",
    ]);

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("page=2"),
      expect.anything(),
    ));

    fireEvent.change(screen.getByLabelText("搜索核查范围"), {
      target: { value: "温室气体" },
    });
    expect(String(fetchMock.mock.lastCall?.[0])).not.toContain(
      encodeURIComponent("温室气体"),
    );
    fireEvent.submit(screen.getByRole("search"));
    await waitFor(() => {
      const url = new URL(String(fetchMock.mock.lastCall?.[0]));
      expect(url.searchParams.get("query")).toBe("温室气体");
      expect(url.searchParams.get("page")).toBe("1");
    });

    const filters = [
      ["单元类型", "assessed", "unit_status"],
      ["当前结论", "unknown", "effective_verdict"],
      ["复核优先级", "high", "review_priority"],
      ["复核状态", "pending_review", "review_status"],
      ["适用性", "undetermined", "applicability_status"],
    ] as const;
    for (const [label, value, parameter] of filters) {
      fireEvent.change(screen.getByLabelText(label), {
        target: { value },
      });
      await waitFor(() => {
        const url = new URL(String(fetchMock.mock.lastCall?.[0]));
        expect(url.searchParams.get(parameter)).toBe(value);
        expect(url.searchParams.get("page")).toBe("1");
      });
    }
  });

  it("distinguishes filtered empty results and clears back to full scope", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = new URL(String(input));
      const filtered = url.searchParams.has("query");
      return Promise.resolve(new Response(JSON.stringify({
        items: filtered ? [] : [{
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
          applicability_status: null,
          source_pdf_pages: [],
        }],
        page: 1,
        page_size: 50,
        total: filtered ? 0 : 577,
      }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<AssessmentTable reportId="report-1" />);
    expect(await screen.findByText("已纳入相关判断")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索核查范围"), {
      target: { value: "无匹配" },
    });
    fireEvent.submit(screen.getByRole("search"));
    expect(await screen.findByText("当前筛选无匹配结果")).toBeInTheDocument();
    expect(screen.queryByText("当前报告暂无 GRI 核查范围")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "清空筛选" }));
    expect(await screen.findByText("共 577 项")).toBeInTheDocument();
    expect(screen.getByText("已纳入相关判断")).toBeInTheDocument();
    const lastUrl = new URL(String(fetchMock.mock.lastCall?.[0]));
    expect(lastUrl.searchParams.has("query")).toBe(false);
  });
});
