import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { RunResult } from "./run-result";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("RunResult", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows run assessments, evidence, recommendations, and export links", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/runs/run-1")) {
          return Promise.resolve(jsonResponse({ run_id: "run-1", report_id: "report-1", status: "completed", confirm_llm: false, started_at: null, completed_at: null, error_message: null }));
        }
        if (url.endsWith("/api/runs/run-1/assessments")) {
          return Promise.resolve(
            jsonResponse([
              {
                assessment_id: "assessment-1",
                run_id: "run-1",
                report_id: "report-1",
                standard_id: "GRI",
                standard_version: "2021",
                disclosure_id: "GRI 302",
                requirement_id: "GRI 302-1-a",
                verdict: "disclosed",
                rationale: "Evidence found.",
                evidence: [{ evidence_id: "evidence-1", run_id: "run-1", report_id: "report-1", source_text: "Energy", source_page: 1, source_file_hash: "hash-1", source_method: "pdfplumber", confidence: 1, is_kpi_evidence: false, quality_flags: [] }],
                missing_items: [],
                model_called: false,
                review_status: "not_required",
              },
            ]),
          );
        }
        if (url.endsWith("/api/runs/run-1/recommendations")) {
          return Promise.resolve(jsonResponse([{ recommendation_id: "rec-1", run_id: "run-1", report_id: "report-1", disclosure_id: "GRI 302", requirement_id: "GRI 302-1-a", recommendation_text: "Improve disclosure.", created_at: null }]));
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    renderWithQuery(<RunResult runId="run-1" />);

    expect(await screen.findByText("GRI 302")).toBeInTheDocument();
    expect(screen.getByText("pdfplumber p.1")).toBeInTheDocument();
    expect(screen.getByText("无需复核")).toBeInTheDocument();
    expect(screen.queryByText("not_required")).not.toBeInTheDocument();
    expect(screen.getByText("Improve disclosure.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Assessments CSV" })).toHaveAttribute("href", "http://localhost:8000/api/exports/runs/run-1/assessments.csv");
  });
});
