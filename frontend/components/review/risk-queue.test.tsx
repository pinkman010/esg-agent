import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { RiskQueue } from "./risk-queue";

describe("RiskQueue", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows paginated high-priority requirements with Chinese business reasons", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const page = Number(new URL(String(input)).searchParams.get("page") ?? "1");
      return Promise.resolve(new Response(JSON.stringify({
      items: [{
        assessment_id: `assessment-${page}`,
        requirement_id: page === 1 ? "GRI 2-1-b" : "GRI 2-51-b",
        requirement_name_zh: "组织所有权与法律形式",
        gri_topic: "GRI 2",
        system_verdict: "unknown",
        reviewed_verdict: null,
        effective_verdict: "unknown",
        risk_level: "high",
        review_priority: "high",
        evidence_status: "conflict",
        applicability_status: "applicable",
        risk_reason_codes: ["sufficiency_conflict"],
        review_status: "pending_review",
        evidence_count: 0,
        source_pdf_pages: [],
        action_status: null,
      }],
      page,
      page_size: 50,
      total: 60,
    }), { status: 200, headers: { "content-type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<RiskQueue reportId="report-1" />);

    expect(await screen.findByText("GRI 2-1-b")).toBeInTheDocument();
    expect(screen.getByText("披露结论与证据充分性冲突")).toBeInTheDocument();
    expect(screen.getByText("第 1–50 条，共 60 条")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(await screen.findByText("GRI 2-51-b")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("page=2"), expect.anything());
  });

  it("batch-confirms the current applicability page with an audit note", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({
          batch_id: "batch-1",
          updated_count: 2,
          assessment_ids: ["assessment-1", "assessment-2"],
        }), { status: 200, headers: { "content-type": "application/json" } }));
      }
      return Promise.resolve(new Response(JSON.stringify({
        items: [1, 2].map((index) => ({
          assessment_id: `assessment-${index}`,
          requirement_id: `GRI 2-${index}-a`,
          requirement_name_zh: `要求 ${index}`,
          gri_topic: "GRI 2",
          system_verdict: "unknown",
          reviewed_verdict: null,
          effective_verdict: "unknown",
          risk_level: "low",
          review_priority: "low",
          evidence_status: "missing",
          applicability_status: "undetermined",
          risk_reason_codes: ["unknown_verdict"],
          review_status: "pending_review",
          evidence_count: 0,
          source_pdf_pages: [],
          action_status: null,
        })),
        page: 1,
        page_size: 50,
        total: 2,
      }), { status: 200, headers: { "content-type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<RiskQueue reportId="report-1" queueType="applicability" reviewerName="张三" />);
    await screen.findByText("GRI 2-1-a");
    fireEvent.change(screen.getByPlaceholderText("批量复核说明（必填）"), {
      target: { value: "本页项目均适用于企业" },
    });
    fireEvent.click(screen.getByRole("button", { name: "批量确认本页为适用" }));

    await waitFor(() => expect(
      fetchMock.mock.calls.some((call) => call[1]?.method === "POST"),
    ).toBe(true));
    const postCall = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    const request = JSON.parse(String(postCall?.[1]?.body));
    expect(request.assessment_ids).toEqual(["assessment-1", "assessment-2"]);
    expect(request.reviewed_applicability_status).toBe("applicable");
    expect(request.reviewer_name).toBe("张三");
  });
});
