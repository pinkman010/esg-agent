import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/tests/render-with-query";
import { ExportVersions } from "./export-versions";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function dashboardResponse(overrides: Record<string, unknown> = {}) {
  return {
    report_id: "report-1",
    run_id: "run-1",
    standard_unit_count: 577,
    verdict_counts: {},
    risk_counts: {},
    review_priority_counts: {},
    high_risk_total: 9,
    high_risk_reviewed: 9,
    high_priority_total: 9,
    high_priority_reviewed: 9,
    high_priority_unresolved: 0,
    applicability_counts: {},
    applicability_undetermined_total: 309,
    failed_requirement_count: 0,
    ...overrides,
  };
}

describe("ExportVersions", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("prevents a formal export request when the dashboard reports unresolved high-priority items", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) {
        return Promise.resolve(jsonResponse(dashboardResponse({
          high_priority_unresolved: 8,
        })));
      }
      if (url.endsWith("/api/reports/report-1/exports")) {
        return Promise.resolve(jsonResponse([]));
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);

    expect(await screen.findByText("正式输出暂不可用：仍有 8 条高优先级项目未完成复核。")).toBeInTheDocument();
    const formalButton = screen.getByRole("button", { name: "生成正式输出" });
    expect(formalButton).toBeDisabled();
    expect(screen.getByRole("button", { name: "生成草稿" })).toBeEnabled();
    fireEvent.click(formalButton);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("prioritizes the analysis-incomplete reason in the formal export preflight", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) {
        return Promise.resolve(jsonResponse(dashboardResponse({
          failed_requirement_count: 2,
          high_priority_unresolved: 5,
        })));
      }
      if (url.endsWith("/api/reports/report-1/exports")) return Promise.resolve(jsonResponse([]));
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);

    expect(await screen.findByText("正式输出暂不可用：仍有 2 条分析失败或未生成结果。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成正式输出" })).toBeDisabled();
  });

  it("keeps formal export disabled when the preflight cannot be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) {
        return Promise.resolve(jsonResponse({ detail: "unavailable" }, 503));
      }
      if (url.endsWith("/api/reports/report-1/exports")) return Promise.resolve(jsonResponse([]));
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);

    expect(await screen.findByText("正式输出门禁读取失败，请刷新页面后重试。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成正式输出" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "生成草稿" })).toBeEnabled();
  });

  it("creates a visibly marked draft export", async () => {
    const draft = { export_id: "export-1", report_id: "report-1", run_id: "run-1", version_number: 0, status: "draft", is_draft: true, file_hash: "hash", engine_version: "rules-v1", risk_rule_version: "risk-v2.1", requirement_version: "gri-eligible-577-v1", review_scope: { draft_label: true, high_priority_total: 12, high_priority_reviewed: 2, high_priority_unresolved: 10, medium_priority_unresolved: 60, applicability_undetermined_total: 343, analysis_incomplete_total: 0, review_scope_statement: "当前仍有高复核优先级未处理 10 条、分析失败或未生成结果 0 条；不代表全部 577 条均已人工确认。" }, file_manifest: [], supersedes_export_id: null, created_by: "张三", created_at: null };
    let exportListCalls = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) return Promise.resolve(jsonResponse(dashboardResponse()));
      if (url.endsWith("/api/reports/report-1/exports/draft") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(draft));
      }
      if (url.endsWith("/api/reports/report-1/exports")) {
        exportListCalls += 1;
        return Promise.resolve(jsonResponse(exportListCalls === 1 ? [] : [draft]));
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);
    fireEvent.click(await screen.findByRole("button", { name: "生成草稿" }));
    expect(await screen.findByText("草稿已生成")).toBeInTheDocument();
    await waitFor(() => expect(exportListCalls).toBe(2));
    expect(screen.getByText("高优先级复核 2/12")).toBeInTheDocument();
    expect(screen.getByText("中优先级未复核 60 · 适用性待判定 343")).toBeInTheDocument();
    expect(screen.getByText("当前仍有高复核优先级未处理 10 条、分析失败或未生成结果 0 条；不代表全部 577 条均已人工确认。")).toBeInTheDocument();
  });

  it("shows the exact formal export gate reason", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) return Promise.resolve(jsonResponse(dashboardResponse()));
      if (url.endsWith("/api/reports/report-1/exports/formal") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ detail: { code: "analysis_incomplete", remaining: 1 } }, 409));
      }
      if (url.endsWith("/api/reports/report-1/exports")) return Promise.resolve(jsonResponse([]));
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);
    expect(await screen.findByText("当前预检通过；提交时仍由后端执行最终门禁校验。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "生成正式输出" }));

    expect(await screen.findByText("正式输出被阻止：仍有 1 条分析失败或未生成结果。")).toBeInTheDocument();
  });

  it("uses review-priority wording for the review gate", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) return Promise.resolve(jsonResponse(dashboardResponse()));
      if (url.endsWith("/api/reports/report-1/exports/formal") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ detail: { code: "high_risk_review_incomplete", remaining: 3 } }, 409));
      }
      if (url.endsWith("/api/reports/report-1/exports")) return Promise.resolve(jsonResponse([]));
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);
    expect(await screen.findByText("当前预检通过；提交时仍由后端执行最终门禁校验。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "生成正式输出" }));

    expect(await screen.findByText("正式输出被阻止：仍有 3 条高优先级项目未完成复核。")).toBeInTheDocument();
    expect(screen.queryByText("高风险")).not.toBeInTheDocument();
  });

  it("shows safe downloadable files with localized names and sizes", async () => {
    const exports = [{
      export_id: "export-2",
      report_id: "report-1",
      run_id: "run-1",
      version_number: 1,
      status: "formal",
      is_draft: false,
      file_hash: "hash",
      engine_version: "rules-v1",
      risk_rule_version: "risk-v2.1",
      requirement_version: "gri-eligible-577-v1",
      review_scope: {
        high_priority_total: 12,
        high_priority_reviewed: 12,
        analysis_incomplete_total: 0,
        review_scope_statement: "高优先级队列已完成；不代表全部 577 项均已人工确认。",
      },
      file_manifest: [
        {
          file_id: "file-assessment",
          filename: "assessment_xlsx.xlsx",
          format: "assessment_xlsx",
          size: 12288,
          sha256: "a".repeat(64),
        },
        {
          file_id: "file-actions",
          filename: "actions_xlsx.xlsx",
          format: "actions_xlsx",
          size: 2048,
          sha256: "b".repeat(64),
        },
        {
          file_id: "file-pdf",
          filename: "management-summary.pdf",
          format: "management_pdf",
          size: 1024,
          sha256: "c".repeat(64),
        },
        {
          file_id: "file-html",
          filename: "print.html",
          format: "print_html",
          size: 512,
          sha256: "d".repeat(64),
        },
      ],
      supersedes_export_id: null,
      created_by: "张三",
      created_at: "2026-07-26T08:00:00Z",
    }];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) return Promise.resolve(jsonResponse(dashboardResponse()));
      if (url.endsWith("/api/reports/report-1/exports")) return Promise.resolve(jsonResponse(exports));
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);

    expect(await screen.findByText("正式版本 v1")).toBeInTheDocument();
    expect(screen.getByText("状态：正式输出")).toBeInTheDocument();
    expect(screen.getByText(/创建人：张三/)).toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
    expect(screen.getByText("高优先级队列已完成；不代表全部 577 项均已人工确认。")).toBeInTheDocument();
    expect(screen.getByText("GRI 核查表（XLSX）")).toBeInTheDocument();
    expect(screen.getByText("整改任务清单（XLSX）")).toBeInTheDocument();
    expect(screen.getByText("管理层摘要（PDF）")).toBeInTheDocument();
    expect(screen.getByText("可打印核查表（HTML）")).toBeInTheDocument();
    expect(screen.getByText("12 KB")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: /下载/ });
    expect(links).toHaveLength(4);
    expect(links[0]).toHaveAttribute(
      "href",
      "http://localhost:8000/api/exports/export-2/files/file-assessment",
    );
    expect(links[0]).toHaveAttribute("download", "assessment_xlsx.xlsx");
    expect(document.body).not.toHaveTextContent("relative_path");
    expect(document.body).not.toHaveTextContent("C:\\");
  });

  it("shows an explicit empty state", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/reports/report-1/dashboard")) return Promise.resolve(jsonResponse(dashboardResponse()));
      if (url.endsWith("/api/reports/report-1/exports")) return Promise.resolve(jsonResponse([]));
      throw new Error(`unexpected request: ${url}`);
    }));

    renderWithQuery(<ExportVersions reportId="report-1" createdBy="张三" />);

    expect(await screen.findByText("尚未生成输出版本")).toBeInTheDocument();
  });
});
