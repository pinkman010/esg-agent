import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReviewEditor } from "./review-editor";

describe("ReviewEditor", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("quick-approves with reviewer identity and optional preset reason", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      snapshot_id: "snapshot-1",
      assessment_id: "assessment-1",
      run_id: "run-1",
      sequence: 1,
      previous_snapshot_id: null,
      operation_type: "approve",
      reviewer_name: "张三",
      reason_code: "system_result_confirmed",
      reviewer_note: "",
      reviewed_verdict: "unknown",
      evidence_pages: null,
      evidence_preview: null,
      rationale: "No evidence.",
      missing_items: [],
      is_batch_operation: false,
      batch_id: null,
      created_at: "2026-07-11T00:00:00Z",
    }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ReviewEditor assessmentId="assessment-1" reviewerName="张三" />);

    fireEvent.click(screen.getByRole("button", { name: "快速通过" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("复核记录已保存")).toBeInTheDocument();
  });

  it("records an independent applicability decision", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      snapshot_id: "snapshot-2",
      assessment_id: "assessment-1",
      run_id: "run-1",
      sequence: 1,
      previous_snapshot_id: null,
      operation_type: "modify",
      reviewer_name: "张三",
      reason_code: "applicability_reviewed",
      reviewer_note: "确认该要求适用",
      reviewed_verdict: null,
      reviewed_applicability_status: "applicable",
      evidence_pages: null,
      evidence_preview: null,
      rationale: null,
      missing_items: null,
      is_batch_operation: false,
      batch_id: null,
      created_at: "2026-07-11T00:00:00Z",
    }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ReviewEditor assessmentId="assessment-1" reviewerName="张三" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "确认该要求适用" } });
    fireEvent.click(screen.getByRole("button", { name: "确认适用" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(request.operation_type).toBe("modify");
    expect(request.reviewed_applicability_status).toBe("applicable");
    expect(await screen.findByText("复核记录已保存")).toBeInTheDocument();
  });
});
