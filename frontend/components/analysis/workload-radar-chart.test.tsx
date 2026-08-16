import { render, screen } from "@testing-library/react";
import type { EChartsOption } from "echarts";
import { describe, expect, it, vi } from "vitest";

import { WorkloadRadarChart } from "./workload-radar-chart";

vi.mock("@/components/charts/echart", () => ({
  EChart: ({ option, className }: { option: EChartsOption; className?: string }) => (
    <div data-testid="echart" data-classname={className}>
      {JSON.stringify(option)}
    </div>
  ),
}));

describe("WorkloadRadarChart", () => {
  it("derives radar indicators from dashboard metrics", () => {
    render(
      <WorkloadRadarChart
        priorities={{ high: 9, medium: 54, low: 436 }}
        applicabilityUndetermined={309}
        analysisIncomplete={2}
      />,
    );

    expect(screen.getByRole("heading", { name: "核查工作负载" })).toBeInTheDocument();
    const chart = screen.getByTestId("echart");
    const option = JSON.parse(chart.textContent ?? "{}") as {
      radar: { indicator: Array<{ name: string; max: number }> };
      series: Array<{ data: Array<{ value: number[] }> }>;
    };
    expect(option.radar.indicator.map((i) => i.name)).toEqual([
      "高优先级",
      "中优先级",
      "低优先级",
      "适用性待判定",
      "分析不完整",
    ]);
    expect(option.series[0].data[0].value).toEqual([9, 54, 436, 309, 2]);
    expect(option.radar.indicator.every((i) => i.max === 436)).toBe(true);
  });

  it("shows empty hint when there is no workload", () => {
    render(<WorkloadRadarChart priorities={{}} applicabilityUndetermined={0} analysisIncomplete={0} />);

    expect(screen.getByText("暂无可汇总结果")).toBeInTheDocument();
    expect(screen.queryByTestId("echart")).not.toBeInTheDocument();
  });
});
