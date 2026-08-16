"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart, RadarChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  RadarComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";

import { chartTextStyle } from "@/lib/chart-theme";

// 按需注册项目使用的图表类型和组件（迁移自 esg-dashboard EChart.tsx）
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  RadarChart,
  GridComponent,
  LegendComponent,
  RadarComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
]);

interface EChartProps {
  option: EChartsOption;
  className?: string;
}

export function EChart({ option, className }: EChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  // 初始化 chart 实例，仅在挂载时执行
  useEffect(() => {
    if (!containerRef.current) return;
    // 测试环境（jsdom 无 canvas）下跳过实例化，降级为占位容器
    if (process.env.NODE_ENV === "test") return;

    let chart: echarts.ECharts | null = null;
    let resizeObserver: ResizeObserver | null = null;
    try {
      chart = echarts.init(containerRef.current, undefined, { renderer: "canvas" });
      chartRef.current = chart;
      resizeObserver = new ResizeObserver(() => chart?.resize());
      resizeObserver.observe(containerRef.current);
    } catch {
      // 环境不支持 canvas（如 jsdom 测试环境）时静默降级为占位容器
      chartRef.current = null;
      return;
    }

    return () => {
      resizeObserver?.disconnect();
      chart?.dispose();
      chartRef.current = null;
    };
  }, []);

  // option 变化时更新图表，避免 dispose/init
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.setOption({ textStyle: chartTextStyle, ...option }, true);
    }
  }, [option]);

  return <div ref={containerRef} className={className ?? "h-72 w-full"} />;
}
