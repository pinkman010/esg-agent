import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { AnalysisProgress } from "./analysis-progress";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

describe("AnalysisProgress", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows seven business stages and retries failed requirements", async () => {
    const run = {
      run_id: "run-1",
      report_id: "report-1",
      status: "partially_completed",
      confirm_llm: false,
      started_at: null,
      completed_at: null,
      error_message: null,
      parent_run_id: null,
      engine_version: "rules-v1",
      risk_rule_version: "risk-v1",
      eligible_requirement_count: 577,
      succeeded_requirement_count: 576,
      failed_requirement_count: 1,
      failure_summary: { failed_requirement_ids: ["GRI 2-1-b"] },
    };
    const stages = [
      { stage_code: "file_validation", status: "completed", completed_units: 1, total_units: 1, error_summary: null, created_at: null },
      { stage_code: "evidence_assessment", status: "partially_failed", completed_units: 577, total_units: 577, error_summary: null, created_at: null },
    ];
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(run))
      .mockResolvedValueOnce(jsonResponse(stages))
      .mockResolvedValueOnce(jsonResponse({ ...run, run_id: "run-2", status: "pending", parent_run_id: "run-1" }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<AnalysisProgress reportId="report-1" runId="run-1" />);

    expect(await screen.findByText("576 / 577 条已生成结果")).toBeInTheDocument();
    expect(screen.getByText("文件检查")).toBeInTheDocument();
    expect(screen.getByText("证据与结论生成")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重跑 1 条失败项" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
