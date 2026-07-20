import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/tests/render-with-query";
import { ActionList } from "./action-list";

describe("ActionList", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("shows improvement actions without changing assessment conclusions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{ action_id: "action-1", report_id: "report-1", assessment_id: "a-1", title: "补充能源核算方法", priority: "high", status: "open", owner_name: "张三", due_date: "2026-08-01", recommendation_text: "补充方法说明", completion_note: null, created_by: "张三", created_at: null, updated_at: null }]), { status: 200, headers: { "content-type": "application/json" } })));
    renderWithQuery(<ActionList reportId="report-1" />);
    expect(await screen.findByText("补充能源核算方法")).toBeInTheDocument();
    expect(screen.getAllByText("待处理").length).toBeGreaterThan(0);
  });

  it("updates task ownership and status with an audit note", async () => {
    let status = "open";
    const action = () => ({ action_id: "action-1", report_id: "report-1", assessment_id: "a-1", title: "补充能源核算方法", priority: "high", status, owner_name: "张三", due_date: "2026-08-01", recommendation_text: "补充方法说明", completion_note: null, created_by: "张三", created_at: null, updated_at: null });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        status = "completed";
        return Promise.resolve(new Response(JSON.stringify(action()), { status: 200, headers: { "content-type": "application/json" } }));
      }
      return Promise.resolve(new Response(JSON.stringify([action()]), { status: 200, headers: { "content-type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ActionList reportId="report-1" />);

    expect(await screen.findByText("补充能源核算方法")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("任务状态：补充能源核算方法"), { target: { value: "completed" } });
    expect(screen.getByRole("button", { name: "保存任务更新" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("状态变更说明：补充能源核算方法"), { target: { value: "已补充并核验" } });
    fireEvent.click(screen.getByRole("button", { name: "保存任务更新" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/actions/action-1"),
      expect.objectContaining({ method: "PATCH" }),
    ));
    const patchCall = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(patchCall?.[1]?.body))).toMatchObject({ status: "completed", owner_name: "张三", completion_note: "已补充并核验" });
    expect(await screen.findByText("任务已更新")).toBeInTheDocument();
  });
});
