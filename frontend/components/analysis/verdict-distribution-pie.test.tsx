import { render, screen } from "@testing-library/react";
import type { EChartsOption } from "echarts";
import { describe, expect, it, vi } from "vitest";

import { VerdictDistributionPie } from "./verdict-distribution-pie";

vi.mock("@/components/charts/echart", () => ({
  EChart: ({ option, className }: { option: EChartsOption; className?: string }) => (
    <div data-testid="echart" data-classname={className}>
      {JSON.stringify(option)}
    </div>
  ),
}));

describe("VerdictDistributionPie", () => {
  it("derives pie data from verdict counts", () => {
    render(
      <VerdictDistributionPie
        counts={{ disclosed: 36, partially_disclosed: 154, not_disclosed: 78, unknown: 309 }}
      />,
    );

    expect(screen.getByRole("heading", { name: "披露结论分布" })).toBeInTheDocument();
    const chart = screen.getByTestId("echart");
    const option = JSON.parse(chart.textContent ?? "{}") as {
      series: Array<{ data: Array<{ name: string; value: number }> }>;
    };
    const series = option.series[0];
    expect(series.data).toHaveLength(4);
    expect(series.data.map((d) => [d.name, d.value])).toEqual([
      ["已披露", 36],
      ["部分披露", 154],
      ["未披露", 78],
      ["待确认", 309],
    ]);
  });

  it("shows empty hint when all counts are zero", () => {
    render(<VerdictDistributionPie counts={{}} />);

    expect(screen.getByText("暂无可汇总结果")).toBeInTheDocument();
    expect(screen.queryByTestId("echart")).not.toBeInTheDocument();
  });
});
