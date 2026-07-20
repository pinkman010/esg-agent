import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { AnalysisProgress } from "./analysis-progress";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

const report = {
  report_id: "report-internal-long-id",
  original_filename: "Envision Energy 2024-zh.pdf",
  file_hash: "hash-1",
  page_count: 78,
  company_name: "远景能源有限公司",
  report_year: 2024,
  language: "zh-CN",
  status: "analysis_completed",
  metadata_detected: {},
  metadata_confirmed_at: null,
  created_at: null,
  updated_at: null,
};

function runResponse(status: string, failedRequirementCount = 0) {
  return {
    run_id: "run-1",
    report_id: report.report_id,
    status,
    confirm_llm: false,
    started_at: null,
    completed_at: null,
    error_message: null,
    parent_run_id: null,
    engine_version: "rules-v1",
    risk_rule_version: "risk-v1",
    eligible_requirement_count: 577,
    succeeded_requirement_count: 577 - failedRequirementCount,
    failed_requirement_count: failedRequirementCount,
    failure_summary: { failed_requirement_ids: failedRequirementCount ? ["GRI 2-1-b"] : [] },
  };
}

function stageResponse() {
  return [
    { stage_code: "file_validation", status: "completed", completed_units: 1, total_units: 1, error_summary: null, created_at: null },
    { stage_code: "pdf_parsing", status: "completed", completed_units: 1, total_units: 1, error_summary: null, created_at: null },
    { stage_code: "report_structure", status: "completed", completed_units: 1, total_units: 1, error_summary: null, created_at: null },
    { stage_code: "requirement_matching", status: "running", completed_units: 50, total_units: 100, error_summary: null, created_at: null },
  ];
}

function stubProgressApi(status: string, failedRequirementCount = 0) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith(`/api/reports/${report.report_id}`)) return Promise.resolve(jsonResponse(report));
    if (url.endsWith("/api/runs/run-1/stages")) return Promise.resolve(jsonResponse(stageResponse()));
    if (url.endsWith("/api/runs/run-1/retry-failed") && init?.method === "POST") {
      return Promise.resolve(jsonResponse({ ...runResponse("pending"), run_id: "run-2" }));
    }
    if (url.endsWith("/api/runs/run-1")) return Promise.resolve(jsonResponse(runResponse(status, failedRequirementCount)));
    throw new Error(`unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("AnalysisProgress", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    router.push.mockReset();
  });

  it("shows business identity and percentage without internal ids or requirement counts", async () => {
    stubProgressApi("running");

    renderWithQuery(<AnalysisProgress reportId={report.report_id} runId="run-1" />);

    expect(await screen.findByText("远景能源有限公司 · 2024 年")).toBeInTheDocument();
    expect(screen.getByText("Envision Energy 2024-zh.pdf")).toBeInTheDocument();
    expect(screen.getByText("分析进度 25%")).toBeInTheDocument();
    expect(screen.getByText("当前阶段：GRI requirement 匹配")).toBeInTheDocument();
    expect(screen.queryByText(report.report_id)).not.toBeInTheDocument();
    expect(screen.queryByText(/577/)).not.toBeInTheDocument();
  });

  it("warns when a running analysis has not emitted a stage event for two minutes", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`/api/reports/${report.report_id}`)) return Promise.resolve(jsonResponse(report));
      if (url.endsWith("/api/runs/run-1/stages")) {
        return Promise.resolve(jsonResponse([
          { stage_code: "evidence_assessment", status: "running", completed_units: 1, total_units: 577, error_summary: null, created_at: "2000-01-01T00:00:00Z" },
        ]));
      }
      if (url.endsWith("/api/runs/run-1")) return Promise.resolve(jsonResponse(runResponse("running")));
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<AnalysisProgress reportId={report.report_id} runId="run-1" />);

    expect(await screen.findByText("分析进度长时间没有更新，后台任务可能已中断。请返回报告列表查看状态。")).toBeInTheDocument();
  });

  it("offers dashboard and high-priority review after completion", async () => {
    stubProgressApi("completed");

    renderWithQuery(<AnalysisProgress reportId={report.report_id} runId="run-1" />);

    expect(await screen.findByText("分析完成")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看分析结果" })).toHaveAttribute("href", `/reports/${report.report_id}/dashboard`);
    expect(screen.getByRole("link", { name: "进入高优先级复核" })).toHaveAttribute("href", `/reports/${report.report_id}/review`);
  });

  it("keeps results available while allowing failed requirements to retry", async () => {
    const fetchMock = stubProgressApi("partially_completed", 1);

    renderWithQuery(<AnalysisProgress reportId={report.report_id} runId="run-1" />);

    expect(await screen.findByText("分析已完成，部分项目需要重跑")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看分析结果" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重跑 1 条失败项" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/retry-failed"), expect.objectContaining({ method: "POST" })));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith(`/reports/${report.report_id}/progress?runId=run-2`));
  });

  it("shows a readable error when progress requests fail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failed")));

    renderWithQuery(<AnalysisProgress reportId={report.report_id} runId="run-1" />);

    expect(await screen.findByText("分析进度读取失败，请稍后重试。")).toBeInTheDocument();
  });

  it("refreshes stale stages once when the run reaches completed", async () => {
    let stageRequests = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`/api/reports/${report.report_id}`)) return Promise.resolve(jsonResponse(report));
      if (url.endsWith("/api/runs/run-1")) return Promise.resolve(jsonResponse(runResponse("completed")));
      if (url.endsWith("/api/runs/run-1/stages")) {
        stageRequests += 1;
        const status = stageRequests === 1 ? "running" : "completed";
        return Promise.resolve(jsonResponse([
          { stage_code: "evidence_assessment", status, completed_units: status === "completed" ? 1 : 0, total_units: 1, error_summary: null, created_at: null },
        ]));
      }
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<AnalysisProgress reportId={report.report_id} runId="run-1" />);

    expect(await screen.findByText("分析完成")).toBeInTheDocument();
    await waitFor(() => expect(stageRequests).toBe(2));
    expect(screen.getByText("证据与结论生成").parentElement).toHaveTextContent("已完成");
    expect(screen.queryByText("进行中")).not.toBeInTheDocument();
  });

  it("does not hide an inconsistent failed stage behind the completed run status", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`/api/reports/${report.report_id}`)) return Promise.resolve(jsonResponse(report));
      if (url.endsWith("/api/runs/run-1")) return Promise.resolve(jsonResponse(runResponse("completed")));
      if (url.endsWith("/api/runs/run-1/stages")) {
        return Promise.resolve(jsonResponse([
          { stage_code: "evidence_assessment", status: "failed", completed_units: 0, total_units: 1, error_summary: "stage failed", created_at: null },
        ]));
      }
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<AnalysisProgress reportId={report.report_id} runId="run-1" />);

    expect(await screen.findByText("分析完成")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("证据与结论生成").parentElement).toHaveTextContent("失败"));
  });
});
