import { describe, expect, it } from "vitest";

import { analysisStages, calculateAnalysisProgress, isAnalysisProgressStalled } from "./progress-model";

const completed = (stage_code: string) => ({
  stage_code,
  status: "completed",
  completed_units: 1,
  total_units: 1,
  error_summary: null,
  created_at: null,
});

describe("calculateAnalysisProgress", () => {
  it("uses the backend eight-stage order", () => {
    expect(analysisStages.map(([code]) => code)).toEqual([
      "file_validation",
      "pdf_parsing",
      "report_structure",
      "requirement_matching",
      "evidence_assessment",
      "risk_classification",
      "ai_assistance",
      "result_summary",
    ]);
  });

  it("uses review-priority wording for the classification stage", () => {
    expect(analysisStages.find(([code]) => code === "risk_classification")?.[1]).toBe("复核优先级计算");
  });

  it("returns zero without stage events", () => {
    expect(calculateAnalysisProgress("running", [])).toEqual({ percent: 0, currentStageCode: null });
  });

  it("uses workload weights for completed stages", () => {
    expect(calculateAnalysisProgress("running", [completed("file_validation")]).percent).toBe(5);
    expect(calculateAnalysisProgress("running", [completed("file_validation"), completed("pdf_parsing")]).percent).toBe(15);
  });

  it("combines completed stage weights with current requirement units", () => {
    const stages = [
      completed("file_validation"),
      completed("pdf_parsing"),
      completed("report_structure"),
      completed("requirement_matching"),
      { stage_code: "evidence_assessment", status: "running", completed_units: 288, total_units: 577, error_summary: null, created_at: null },
    ];

    expect(calculateAnalysisProgress("running", stages)).toEqual({ percent: 57, currentStageCode: "evidence_assessment" });
  });

  it("forces successful and partial terminal runs to one hundred percent", () => {
    expect(calculateAnalysisProgress("completed", []).percent).toBe(100);
    expect(calculateAnalysisProgress("partially_completed", []).percent).toBe(100);
  });

  it("keeps failed runs at their completed stage percentage", () => {
    const stages = [
      completed("file_validation"),
      completed("pdf_parsing"),
      { stage_code: "report_structure", status: "failed", completed_units: 0, total_units: 1, error_summary: "failed", created_at: null },
    ];

    expect(calculateAnalysisProgress("failed", stages)).toEqual({ percent: 15, currentStageCode: "report_structure" });
  });

  it("clamps current stage units and ignores zero totals", () => {
    const over = [{ stage_code: "file_validation", status: "running", completed_units: 2, total_units: 1, error_summary: null, created_at: null }];
    const zero = [{ stage_code: "file_validation", status: "running", completed_units: 1, total_units: 0, error_summary: null, created_at: null }];

    expect(calculateAnalysisProgress("running", over).percent).toBe(5);
    expect(calculateAnalysisProgress("running", zero).percent).toBe(0);
  });

  it("prefers a later running stage over an earlier partially failed stage", () => {
    const stages = [
      completed("file_validation"),
      completed("pdf_parsing"),
      completed("report_structure"),
      completed("requirement_matching"),
      { stage_code: "evidence_assessment", status: "partially_failed", completed_units: 90, total_units: 100, error_summary: "one failed", created_at: null },
      { stage_code: "risk_classification", status: "running", completed_units: 50, total_units: 100, error_summary: null, created_at: null },
    ];

    expect(calculateAnalysisProgress("running", stages)).toEqual({ percent: 87, currentStageCode: "risk_classification" });
  });

  it("counts a skipped AI stage as complete without pretending it called a model", () => {
    const stages = [
      completed("file_validation"),
      completed("pdf_parsing"),
      completed("report_structure"),
      completed("requirement_matching"),
      completed("evidence_assessment"),
      completed("risk_classification"),
      { ...completed("ai_assistance"), status: "skipped" },
    ];

    expect(calculateAnalysisProgress("running", stages)).toEqual({ percent: 95, currentStageCode: null });
  });

  it("does not move backwards as a run advances through stages", () => {
    const snapshots = [
      [completed("file_validation")],
      [completed("file_validation"), completed("pdf_parsing")],
      [completed("file_validation"), completed("pdf_parsing"), completed("report_structure"), completed("requirement_matching")],
      [completed("file_validation"), completed("pdf_parsing"), completed("report_structure"), completed("requirement_matching"),
        { stage_code: "evidence_assessment", status: "running", completed_units: 300, total_units: 577, error_summary: null, created_at: null }],
    ];
    const percentages = snapshots.map((stages) => calculateAnalysisProgress("running", stages).percent);

    expect(percentages).toEqual([5, 15, 30, 58]);
  });

  it("marks only stale running runs as stalled", () => {
    const now = new Date("2026-07-15T08:05:00Z");
    const staleStage = [{ stage_code: "evidence_assessment", status: "running", completed_units: 1, total_units: 577, error_summary: null, created_at: "2026-07-15T08:02:59Z" }];
    const freshStage = [{ ...staleStage[0], created_at: "2026-07-15T08:03:01Z" }];

    expect(isAnalysisProgressStalled("running", staleStage, now)).toBe(true);
    expect(isAnalysisProgressStalled("running", freshStage, now)).toBe(false);
    expect(isAnalysisProgressStalled("pending", staleStage, now)).toBe(false);
    expect(isAnalysisProgressStalled("failed", staleStage, now)).toBe(false);
    expect(isAnalysisProgressStalled("completed", staleStage, now)).toBe(false);
    expect(isAnalysisProgressStalled("running", [{ ...staleStage[0], created_at: null }], now)).toBe(false);
  });
});
