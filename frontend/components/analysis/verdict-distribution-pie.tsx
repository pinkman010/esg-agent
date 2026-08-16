"use client";

import type { EChartsOption } from "echarts";

import { EChart } from "@/components/charts/echart";
import { Panel } from "@/components/ui/panel";
import { chartLegend, chartPalette, chartPieItemStyle, chartTooltip } from "@/lib/chart-theme";

const verdictItems = [
  { key: "disclosed", label: "已披露", color: chartPalette.semantic.positive },
  { key: "partially_disclosed", label: "部分披露", color: chartPalette.semantic.warning },
  { key: "not_disclosed", label: "未披露", color: chartPalette.semantic.negative },
  { key: "unknown", label: "待确认", color: chartPalette.semantic.neutral },
] as const;

export function VerdictDistributionPie({ counts }: { counts: Record<string, number> }) {
  const data = verdictItems
    .map((item) => ({ name: item.label, value: counts[item.key] ?? 0, itemStyle: { color: item.color } }))
    .filter((item) => item.value > 0);
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <Panel title="披露结论分布" contentClassName="min-h-[288px]">
      {total === 0 ? (
        <p className="rounded-lg bg-muted/60 p-4 text-sm text-muted-foreground">暂无可汇总结果</p>
      ) : (
        <EChart
          className="h-72 w-full"
          option={{
            tooltip: { ...chartTooltip, trigger: "item" },
            legend: chartLegend,
            series: [
              {
                type: "pie",
                radius: ["42%", "68%"],
                center: ["50%", "46%"],
                itemStyle: chartPieItemStyle,
                label: { formatter: "{b}\n{d}%", fontSize: 11, color: "#475569" },
                data,
              },
            ],
          } satisfies EChartsOption}
        />
      )}
    </Panel>
  );
}
