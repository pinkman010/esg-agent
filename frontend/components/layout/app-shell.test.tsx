import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithQuery } from "@/tests/render-with-query";
import { AppShell } from "./app-shell";

let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("AppShell", () => {
  afterEach(() => {
    pathname = "/";
    vi.unstubAllGlobals();
  });

  it("shows global navigation without a fictional report context", () => {
    renderWithQuery(<AppShell><p>页面内容</p></AppShell>);

    expect(screen.getAllByRole("link", { name: "工作台首页" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "ESG 报告" }).length).toBeGreaterThan(0);
    expect(screen.queryByText("当前报告")).not.toBeInTheDocument();
    expect(screen.queryByText(/499|78 个上下文|esg_agent_demo/)).not.toBeInTheDocument();
  });

  it("keeps the desktop sidebar artwork sized to the viewport", () => {
    const { container } = renderWithQuery(<AppShell><p>页面内容</p></AppShell>);

    const sidebarNavigation = screen.getByRole("navigation", { name: "页面导航" });
    const sidebar = sidebarNavigation.closest("aside");
    const sidebarArtwork = container.querySelector('img[src*="sidebar-renewable-energy"]');

    expect(sidebar).not.toBeNull();
    expect(sidebar?.firstElementChild).toHaveClass(
      "sticky",
      "top-16",
      "h-[calc(100vh-4rem)]",
      "overflow-hidden",
    );
    expect(sidebarArtwork).toHaveClass("opacity-50");
    expect(
      Array.from(sidebarArtwork?.parentElement?.children ?? []).some(
        (element) => typeof element.className === "string" && element.className.includes("gradient"),
      ),
    ).toBe(false);
  });

  it("loads the current report and exposes report-scoped navigation", async () => {
    pathname = "/reports/report-1/dashboard";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      report_id: "report-1",
      original_filename: "Envision Energy 2024-zh.pdf",
      file_hash: "hash-1",
      page_count: 78,
      company_name: "远景能源有限公司",
      report_year: 2024,
      language: "zh-CN",
      status: "analysis_completed",
      metadata_detected: {},
      metadata_confirmed_at: "2026-07-26T00:00:00Z",
      created_at: "2026-07-26T00:00:00Z",
      updated_at: "2026-07-26T00:00:00Z",
    })));

    renderWithQuery(<AppShell><p>页面内容</p></AppShell>);

    expect(await screen.findByText("远景能源有限公司 · 2024 年")).toBeInTheDocument();
    expect(screen.getByText("分析已完成")).toBeInTheDocument();
    expect(screen.getByText("当前报告")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "报告总览" })).toHaveAttribute(
      "href",
      "/reports/report-1/dashboard",
    );
    expect(screen.getByRole("link", { name: "完整核查" })).toHaveAttribute(
      "href",
      "/reports/report-1/assessments",
    );
    expect(screen.getByRole("link", { name: "人工复核" })).toHaveAttribute(
      "href",
      "/reports/report-1/review",
    );
    expect(screen.getByRole("link", { name: "整改任务" })).toHaveAttribute(
      "href",
      "/reports/report-1/actions",
    );
    expect(screen.getByRole("link", { name: "输出版本" })).toHaveAttribute(
      "href",
      "/reports/report-1/exports",
    );
    expect(screen.getByRole("link", { name: "报告总览" })).toHaveAttribute("aria-current", "page");
  });

  it("keeps global navigation usable when report context fails", async () => {
    pathname = "/reports/report-1/review";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not found", { status: 404 })));

    renderWithQuery(<AppShell><p>页面内容</p></AppShell>);

    expect(await screen.findByText("报告上下文加载失败")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "ESG 报告" }).length).toBeGreaterThan(0);
  });
});
