import type { EChartsOption } from "echarts";

/**
 * 统一图表语义色板（迁移自 esg-dashboard src/lib/chartTheme.ts）
 *
 * 设计原则：
 * - 正/良/通过 → 品牌 emerald 绿系（与 globals.css --accent 同色系）
 * - 负/差/缺失 → rose/red 系（对应 --priority-high）
 * - 中/警告 → amber 系（对应 --priority-medium）
 * - 信息/中性 → sky/slate 系（对应 --applicability）
 * - 同一图表内避免高饱和色直接相邻
 *
 * 说明：ECharts 需要具体颜色值，此处保留 hex；
 * 对应的 HSL 业务变量见 app/globals.css（--gap-*、--priority-*、--applicability）。
 */

export const chartPalette = {
  /** 披露属性柱状图（8柱：4对 缺口/完整） */
  requirementBar: [
    "#f43f5e", // 强制缺口     rose-500
    "#10b981", // 强制完整     emerald-500
    "#fb923c", // 条件性缺口   orange-400
    "#34d399", // 条件性完整   emerald-400
    "#fbbf24", // 自愿缺口     amber-400
    "#6ee7b7", // 自愿完整     emerald-300
    "#f87171", // 待确认缺口   red-400
    "#a7f3d0", // 待确认完整   emerald-200
  ],

  /** 风险趋势折线图（高/中/低） */
  riskLine: ["#f43f5e", "#f59e0b", "#10b981"],

  /** 人工复核状态饼图（待复核/已通过/已修改/不采纳） */
  reviewPie: [
    "#f59e0b", // 待复核  amber-500
    "#10b981", // 已通过  emerald-500
    "#0ea5e9", // 已修改  sky-500
    "#f43f5e", // 不采纳  rose-500
  ],

  /** 差距等级色条（重大/轻微/待确认/无） */
  gapLevel: {
    major: "#f43f5e",
    minor: "#f59e0b",
    pending: "#0ea5e9",
    none: "#10b981",
  },

  /** 通用语义色 */
  semantic: {
    positive: "#10b981",
    positiveLight: "#34d399",
    warning: "#f59e0b",
    negative: "#f43f5e",
    info: "#0ea5e9",
    neutral: "#94a3b8",
  },
} as const;

export const chartTextStyle = {
  color: "#334155",
  fontFamily:
    '"Segoe UI Variable", "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", Arial, sans-serif',
  fontSize: 12,
};

export const chartTooltip: NonNullable<EChartsOption["tooltip"]> = {
  backgroundColor: "rgba(255,255,255,0.96)",
  borderColor: "#e2e8f0",
  borderWidth: 1,
  padding: [8, 10],
  textStyle: {
    color: "#334155",
    fontSize: 12,
  },
  extraCssText: "box-shadow:0 8px 24px rgba(15,23,42,0.10);border-radius:6px;",
};

export const chartLegend = {
  bottom: 0,
  itemWidth: 10,
  itemHeight: 10,
  itemGap: 16,
  textStyle: {
    color: "#64748b",
    fontSize: 12,
  },
};

export const chartGrid = {
  left: 36,
  right: 18,
  top: 22,
  bottom: 46,
};

export const chartCategoryAxis = {
  axisLine: {
    lineStyle: { color: "rgba(148,163,184,0.45)" },
  },
  axisTick: {
    show: false,
  },
  axisLabel: {
    color: "#64748b",
    fontSize: 11,
  },
  splitLine: {
    show: false,
  },
};

export const chartValueAxis = {
  axisLine: {
    show: false,
  },
  axisTick: {
    show: false,
  },
  axisLabel: {
    color: "#64748b",
    fontSize: 11,
  },
  splitLine: {
    lineStyle: {
      color: "rgba(226,232,240,0.86)",
    },
  },
};

export const chartRadarStyle = {
  splitNumber: 4,
  splitLine: {
    lineStyle: { color: "rgba(226,232,240,0.92)" },
  },
  splitArea: {
    areaStyle: {
      color: ["rgba(248,250,252,0.82)", "rgba(255,255,255,0.92)"],
    },
  },
  axisLine: {
    lineStyle: { color: "rgba(203,213,225,0.70)" },
  },
  axisName: {
    color: "#64748b",
    fontSize: 12,
  },
};

export const chartPieItemStyle = {
  borderColor: "#ffffff",
  borderWidth: 3,
  borderRadius: 6,
};

export const chartCenterTitle = {
  textStyle: {
    color: "#0f172a",
    fontSize: 24,
    fontWeight: 700,
  },
  subtextStyle: {
    color: "#64748b",
    fontSize: 12,
    fontWeight: 500,
  },
};
