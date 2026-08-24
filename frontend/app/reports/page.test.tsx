import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportsPage from "./page";

vi.mock("@/components/reports/report-list", () => ({
  ReportList: () => <div>报告列表内容</div>,
}));
vi.mock("@/components/upload/report-upload-panel", () => ({
  ReportUploadPanel: () => <div>报告上传内容</div>,
}));

describe("ReportsPage", () => {
  it("uses the static disclosure hero while preserving report operations", () => {
    const { container } = render(<ReportsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "ESG 报告" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByText("上传报告、确认信息，并从当前业务状态继续 GRI 核查。"),
    ).toBeInTheDocument();
    expect(screen.getByText("报告列表内容")).toBeInTheDocument();
    expect(screen.getByText("报告上传内容")).toBeInTheDocument();

    const artwork = container.querySelector(
      'img[src*="module-policy-disclosure"]',
    );
    expect(artwork).toHaveAttribute("alt", "");
    expect(artwork).toHaveAttribute("loading", "eager");
    expect(artwork).toHaveClass("opacity-[0.23]");
    expect(artwork).not.toHaveClass("animate-ken-burns");
    expect(container.querySelector('[class*="linear-gradient"]')).toBeNull();
  });
});
