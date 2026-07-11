import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/tests/render-with-query";
import { ActionList } from "./action-list";

describe("ActionList", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("shows improvement actions without changing assessment conclusions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{ action_id: "action-1", report_id: "report-1", assessment_id: "a-1", title: "补充能源核算方法", priority: "high", status: "open", owner_name: "张三", due_date: "2026-08-01", recommendation_text: "补充方法说明", completion_note: null, created_by: "张三", created_at: null, updated_at: null }]), { status: 200, headers: { "content-type": "application/json" } })));
    renderWithQuery(<ActionList reportId="report-1" />);
    expect(await screen.findByText("补充能源核算方法")).toBeInTheDocument();
    expect(screen.getByText("待处理")).toBeInTheDocument();
  });
});
