"use client";

import type { EChartsOption } from "echarts";

import { EChart } from "@/components/charts/echart";
import { Panel } from "@/components/ui/panel";
import { chartPalette, chartRadarStyle, chartTooltip } from "@/lib/chart-theme";

export function WorkloadRadarChart({
  priorities,
  applicabilityUndetermined,
  analysisIncomplete,
}: {
  priorities: Record<string, number>;
  applicabilityUndetermined: number;
  analysisIncomplete: number;
}) {
  const axes = [
    { name: "高优先级", value: priorities.high ?? 0 },
    { name: "中优先级", value: priorities.medium ?? 0 },
    { name: "低优先级", value: priorities.low ?? 0 },
    { name: "适用性待判定", value: applicabilityUndetermined },
    { name: "分析不完整", value: analysisIncomplete },
  ];
  const total = axes.reduce((sum, axis) => sum + axis.value, 0);
  const max = Math.max(...axes.map((axis) => axis.value), 1);

  return (
    <Panel
      title="核查工作负载"
      showInfo
      infoTip="从现有总览数据推导：优先级分布、适用性待判定与分析不完整数量，用于安排人工复核投入。"
      contentClassName="min-h-[288px]"
    >
      {total === 0 ? (
        <p className="rounded-lg bg-muted/60 p-4 text-sm text-muted-foreground">暂无可汇总结果</p>
      ) : (
        <EChart
          className="h-72 w-full"
          option={{
            tooltip: { ...chartTooltip, trigger: "item" },
            radar: {
              ...chartRadarStyle,
              indicator: axes.map((axis) => ({ name: axis.name, max })),
            },
            series: [
              {
                type: "radar",
                data: [
                  {
                    name: "工作负载",
                    value: axes.map((axis) => axis.value),
                    itemStyle: { color: chartPalette.semantic.info },
                    areaStyle: { color: "rgba(14,165,233,0.12)" },
                  },
                ],
              },
            ],
          } satisfies EChartsOption}
        />
      )}
    </Panel>
  );
}
