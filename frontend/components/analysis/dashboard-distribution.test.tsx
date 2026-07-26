import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardDistribution } from "./dashboard-distribution";

describe("DashboardDistribution", () => {
  it("shows counts and percentages using the actual distribution total", () => {
    render(
      <DashboardDistribution
        title="披露结论"
        description="499 个独立判断项的当前规则结论"
        counts={{ disclosed: 36, partially_disclosed: 154, unknown: 309 }}
        items={[
          { key: "disclosed", label: "已披露", tone: "success" },
          { key: "partially_disclosed", label: "部分披露", tone: "warning" },
          { key: "unknown", label: "待确认", tone: "neutral" },
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "披露结论" })).toBeInTheDocument();
    expect(screen.getByText("已披露")).toBeInTheDocument();
    expect(screen.getByText("36")).toBeInTheDocument();
    expect(screen.getByText("7.2%")).toBeInTheDocument();
    expect(screen.getByText("154")).toBeInTheDocument();
    expect(screen.getByText("30.9%")).toBeInTheDocument();
    expect(screen.getByText("309")).toBeInTheDocument();
    expect(screen.getByText("61.9%")).toBeInTheDocument();
  });

  it("shows an explicit empty distribution", () => {
    render(
      <DashboardDistribution
        title="复核优先级"
        description="当前没有独立判断结果"
        counts={{}}
        items={[{ key: "high", label: "高优先级", tone: "danger" }]}
      />,
    );

    expect(screen.getByText("暂无可汇总结果")).toBeInTheDocument();
  });
});
