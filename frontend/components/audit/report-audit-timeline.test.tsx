import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportAuditTimeline } from "./report-audit-timeline";


describe("ReportAuditTimeline", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("presents report events in Chinese without rendering raw JSON", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      items: [
        {
          audit_event_id: 5,
          run_id: "run-2",
          event_type: "formal_export_created",
          payload: {
            export_id: "export-2",
            version_number: 1,
            supersedes_export_id: null,
          },
          created_at: "2026-07-29T05:00:00Z",
        },
        {
          audit_event_id: 4,
          run_id: "run-2",
          event_type: "review_snapshot_created",
          payload: {
            snapshot_id: "snapshot-1",
            assessment_id: "assessment-1",
            requirement_id: "GRI 2-2-a",
            operation_type: "approve",
          },
          created_at: "2026-07-29T04:00:00Z",
        },
        {
          audit_event_id: 3,
          run_id: "run-2",
          event_type: "analysis_retry_created",
          payload: {
            retry_requirement_count: 2,
            reason: "修复后重跑",
          },
          created_at: "2026-07-29T03:00:00Z",
        },
        {
          audit_event_id: 2,
          run_id: "run-1",
          event_type: "analysis_failed",
          payload: {
            error_code: "analysis_execution_failed",
            failed_requirement_ids: ["GRI 2-1-a"],
          },
          created_at: "2026-07-29T02:00:00Z",
        },
      ],
      total: 4,
      offset: 0,
      limit: 20,
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    })));
    vi.stubGlobal("fetch", fetchMock);

    const view = renderWithQuery(
      <ReportAuditTimeline reportId="report-1" />,
    );

    expect(await screen.findByText("失败项目重跑已创建")).toBeInTheDocument();
    expect(screen.getByText("分析执行失败")).toBeInTheDocument();
    expect(screen.getByText("人工复核快照已保存")).toBeInTheDocument();
    expect(screen.getByText("正式输出已生成")).toBeInTheDocument();
    expect(screen.getByText("快照")).toBeInTheDocument();
    expect(screen.getByText("操作类型")).toBeInTheDocument();
    expect(screen.getByText("版本号")).toBeInTheDocument();
    expect(screen.getByText("替代的输出版本")).toBeInTheDocument();
    expect(screen.getByText("重跑项目数")).toBeInTheDocument();
    expect(screen.getByText("失败核查项")).toBeInTheDocument();
    expect(screen.getAllByText("核查项")).toHaveLength(2);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("GRI 2-1-a")).toBeInTheDocument();
    expect(view.container.querySelector("pre")).toBeNull();
    expect(view.container.textContent).not.toContain('{"');
  });

  it("requests the next page and reports an empty timeline", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const offset = Number(
        new URL(String(input)).searchParams.get("offset") ?? "0",
      );
      return Promise.resolve(new Response(JSON.stringify({
        items: offset === 0 ? [{
          audit_event_id: 1,
          run_id: null,
          event_type: "report_uploaded",
          payload: {},
          created_at: null,
        }] : [],
        total: offset === 0 ? 21 : 0,
        offset,
        limit: 20,
      }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<ReportAuditTimeline reportId="report-1" />);

    expect(await screen.findByText("报告已上传")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    await waitFor(() => {
      const url = new URL(String(fetchMock.mock.lastCall?.[0]));
      expect(url.searchParams.get("offset")).toBe("20");
    });
    expect(await screen.findByText("当前报告暂无审计事件")).toBeInTheDocument();
  });

  it("explains when the running backend does not expose the audit route", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      detail: "Not Found",
    }), {
      status: 404,
      headers: { "content-type": "application/json" },
    }))));

    renderWithQuery(<ReportAuditTimeline reportId="report-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "当前服务版本与页面不一致，请重启后端服务后重试。",
    );
  });
});
