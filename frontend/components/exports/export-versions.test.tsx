import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/tests/render-with-query";
import { ExportVersions } from "./export-versions";

describe("ExportVersions", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("creates a visibly marked draft export", async () => {
    const draft = { export_id: "export-1", report_id: "report-1", run_id: "run-1", version_number: 0, status: "draft", is_draft: true, file_hash: "hash", engine_version: "rules-v1", risk_rule_version: "risk-v2.1", requirement_version: "gri-eligible-577-v1", review_scope: { draft_label: true, high_priority_total: 12, high_priority_reviewed: 2, high_priority_unresolved: 10, medium_priority_unresolved: 60, applicability_undetermined_total: 343, analysis_incomplete_total: 0, review_scope_statement: "当前仍有高复核优先级未处理 10 条、分析失败或未生成结果 0 条；不代表全部 577 条均已人工确认。" }, file_manifest: [], supersedes_export_id: null, created_by: "张三", created_at: null };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("[]", { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(draft), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([draft]), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);
    fireEvent.click(await screen.findByRole("button", { name: "生成草稿" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(await screen.findByText("草稿已生成")).toBeInTheDocument();
    expect(screen.getByText("高优先级复核 2/12")).toBeInTheDocument();
    expect(screen.getByText("中优先级未复核 60 · 适用性待判定 343")).toBeInTheDocument();
    expect(screen.getByText("当前仍有高复核优先级未处理 10 条、分析失败或未生成结果 0 条；不代表全部 577 条均已人工确认。")).toBeInTheDocument();
  });

  it("shows the exact formal export gate reason", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("[]", { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: { code: "analysis_incomplete", remaining: 1 },
      }), { status: 409, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);
    fireEvent.click(await screen.findByRole("button", { name: "生成正式输出" }));

    expect(await screen.findByText("正式输出被阻止：仍有 1 条分析失败或未生成结果。")).toBeInTheDocument();
  });
});
