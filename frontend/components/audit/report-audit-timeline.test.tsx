import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { ReportAuditTimeline } from "./report-audit-timeline";


describe("ReportAuditTimeline", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("hides internal identifiers and unknown payload fields from the product timeline", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      items: [{
        audit_event_id: 6,
        run_id: "run-92bf75b11eb042dab6cb689311634fe1",
        event_type: "improvement_action_created",
        payload: {
          action_id: "action-aa6cf4f5b5f545d98f18336a551e77d8",
          report_id: "report-15401bb4334e40d4a0885730f2635b22",
          file_id: "file-1a2b3c",
          profile_id: "profile-4d5e6f",
          requirement_id: "GRI 2-27-a-i",
          reason: "报告 report-15401bb4334e40d4a0885730f2635b22 的运行 run-92bf75b11eb042dab6cb689311634fe1 不可用",
          constructor: "should-not-render-either",
          internal_debug_field: "should-not-render",
        },
        created_at: "2026-07-29T06:00:00Z",
      }],
      total: 1,
      offset: 0,
      limit: 20,
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }))));

    const view = renderWithQuery(<ReportAuditTimeline reportId="report-1" />);

    expect(await screen.findByText("整改任务已创建")).toBeInTheDocument();
    expect(screen.getByText("GRI 2-27-a-i")).toBeInTheDocument();
    expect(view.container.textContent).not.toContain("run-92bf75b11eb042dab6cb689311634fe1");
    expect(view.container.textContent).not.toContain("action-aa6cf4f5b5f545d98f18336a551e77d8");
    expect(view.container.textContent).not.toContain("report-15401bb4334e40d4a0885730f2635b22");
    expect(view.container.textContent).not.toContain("file-1a2b3c");
    expect(view.container.textContent).not.toContain("profile-4d5e6f");
    expect(view.container.textContent).not.toContain("internal_debug_field");
    expect(view.container.textContent).not.toContain("should-not-render");
    expect(screen.getByText("报告 [内部标识已隐藏] 的运行 [内部标识已隐藏] 不可用")).toBeInTheDocument();
  });

  it("keeps registered business changes and localizes their values", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      items: [
        {
          audit_event_id: 8,
          run_id: "run-2",
          event_type: "improvement_action_updated",
          payload: {
            action_id: "action-2",
            changed_fields: ["due_date", "owner_name", "status"],
            old_due_date: "2026-08-01",
            new_due_date: "2026-08-15",
            old_owner_name: "张三",
            new_owner_name: "李四",
            old_status: "open",
            new_status: "in_progress",
          },
          created_at: "2026-07-29T08:00:00Z",
        },
        {
          audit_event_id: 7,
          run_id: "run-2",
          event_type: "applicability_batch_reviewed",
          payload: {
            assessment_count: 3,
            reviewed_applicability_status: "not_applicable_confirmed",
          },
          created_at: "2026-07-29T07:00:00Z",
        },
      ],
      total: 2,
      offset: 0,
      limit: 20,
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }))));

    renderWithQuery(<ReportAuditTimeline reportId="report-1" />);

    expect(await screen.findByText("整改任务已更新")).toBeInTheDocument();
    expect(screen.getByText("原截止日期")).toBeInTheDocument();
    expect(screen.getByText("新截止日期")).toBeInTheDocument();
    expect(screen.getByText("原负责人")).toBeInTheDocument();
    expect(screen.getByText("新负责人")).toBeInTheDocument();
    expect(screen.getByText("2026-08-01")).toBeInTheDocument();
    expect(screen.getByText("2026-08-15")).toBeInTheDocument();
    expect(screen.getByText("张三")).toBeInTheDocument();
    expect(screen.getByText("李四")).toBeInTheDocument();
    expect(screen.getByText("截止日期、负责人、状态")).toBeInTheDocument();
    expect(screen.getByText("待处理")).toBeInTheDocument();
    expect(screen.getByText("进行中")).toBeInTheDocument();
    expect(screen.getByText("人工确认不适用")).toBeInTheDocument();
  });

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
    expect(screen.getByText("操作类型")).toBeInTheDocument();
    expect(screen.getByText("版本号")).toBeInTheDocument();
    expect(screen.getByText("重跑项目数")).toBeInTheDocument();
    expect(screen.getByText("失败核查项")).toBeInTheDocument();
    expect(screen.getByText("核查项")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("GRI 2-1-a")).toBeInTheDocument();
    expect(view.container.textContent).not.toContain("run-2");
    expect(view.container.textContent).not.toContain("snapshot-1");
    expect(view.container.textContent).not.toContain("assessment-1");
    expect(view.container.textContent).not.toContain("export-2");
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
