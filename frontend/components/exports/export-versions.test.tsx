import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/tests/render-with-query";
import { ExportVersions } from "./export-versions";

describe("ExportVersions", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("creates a visibly marked draft export", async () => {
    const draft = { export_id: "export-1", report_id: "report-1", run_id: "run-1", version_number: 0, status: "draft", is_draft: true, file_hash: "hash", engine_version: "rules-v1", risk_rule_version: "risk-v1", requirement_version: "gri-eligible-577-v1", review_scope: { draft_label: true, high_risk_total: 1, high_risk_reviewed: 0 }, file_manifest: [], supersedes_export_id: null, created_by: "张三", created_at: null };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("[]", { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(draft), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([draft]), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);
    fireEvent.click(await screen.findByRole("button", { name: "生成草稿" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(await screen.findByText("草稿已生成")).toBeInTheDocument();
  });
});
