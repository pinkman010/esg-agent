import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ActionsPage from "./actions/page";
import AuditPage from "./audit/page";
import ExportsPage from "./exports/page";

vi.mock("@/components/actions/action-list", () => ({
  ActionList: () => <div>任务列表</div>,
}));
vi.mock("@/components/exports/export-versions", () => ({
  ExportVersions: () => <div>输出列表</div>,
}));
vi.mock("@/components/audit/report-audit-timeline", () => ({
  ReportAuditTimeline: () => <div>审计列表</div>,
}));

function reportParams() {
  return Promise.resolve({ reportId: "report-1" });
}

describe("report workspace page heroes", () => {
  it("maps the monitoring artwork to actions", async () => {
    const { container } = render(
      await ActionsPage({ params: reportParams() }),
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "整改任务" }),
    ).toBeInTheDocument();
    const artwork = container.querySelector('img[src*="module-claw-monitor"]');
    expect(artwork).toHaveClass("opacity-[0.23]");
    expect(artwork).not.toHaveClass("animate-ken-burns");
  });

  it("maps the disclosure artwork to exports", async () => {
    const { container } = render(
      await ExportsPage({ params: reportParams() }),
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "输出与版本" }),
    ).toBeInTheDocument();
    const artwork = container.querySelector(
      'img[src*="module-policy-disclosure"]',
    );
    expect(artwork).toHaveClass("opacity-[0.23]");
    expect(artwork).not.toHaveClass("animate-ken-burns");
  });

  it("maps the monitoring artwork to audit", async () => {
    const { container } = render(
      await AuditPage({ params: reportParams() }),
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "审计时间线" }),
    ).toBeInTheDocument();
    const artwork = container.querySelector('img[src*="module-claw-monitor"]');
    expect(artwork).toHaveClass("opacity-[0.23]");
    expect(artwork).not.toHaveClass("animate-ken-burns");
  });
});
