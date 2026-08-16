"use client";

import { useMemo } from "react";
import type { ReactNode } from "react";

import { useCountUp } from "@/lib/hooks/use-count-up";

const toneStyles = {
  neutral: {
    border: "border-l-slate-400",
    accent: "bg-slate-400",
    icon: "bg-slate-50 text-slate-600 ring-slate-200",
    spark: "#64748b",
  },
  danger: {
    border: "border-l-red-500",
    accent: "bg-rose-500",
    icon: "bg-rose-50 text-rose-700 ring-rose-100",
    spark: "#e11d48",
  },
  warning: {
    border: "border-l-amber-500",
    accent: "bg-amber-500",
    icon: "bg-amber-50 text-amber-700 ring-amber-100",
    spark: "#d97706",
  },
  success: {
    border: "border-l-emerald-600",
    accent: "bg-emerald-500",
    icon: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    spark: "#059669",
  },
  info: {
    border: "border-l-sky-500",
    accent: "bg-sky-500",
    icon: "bg-sky-50 text-sky-700 ring-sky-100",
    spark: "#0284c7",
  },
} as const;

export type MetricCardTone = keyof typeof toneStyles;

function Sparkline({ data, tone }: { data: number[]; tone: MetricCardTone }) {
  const color = toneStyles[tone].spark;
  const points = useMemo(() => {
    const safeData = data.length > 0 ? data : [0];
    const min = Math.min(...safeData);
    const max = Math.max(...safeData);
    const range = max - min || 1;
    const width = 88;
    const height = 32;
    const steps = Math.max(safeData.length - 1, 1);

    return safeData
      .map((v, i) => {
        const x = (i / steps) * width;
        const y = height - ((v - min) / range) * height;
        return `${x},${y}`;
      })
      .join(" ");
  }, [data]);
  const areaPoints = `0,32 ${points} 88,32`;

  return (
    <svg width={88} height={32} viewBox="0 0 88 32" className="overflow-visible opacity-80" aria-hidden="true">
      <polygon points={areaPoints} fill={color} opacity="0.05" />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={5}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.10"
      />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function MetricCard({
  label,
  value,
  description,
  icon,
  tone = "neutral",
  sparkline,
  delta,
  animate = true,
}: {
  label: string;
  value: ReactNode;
  description?: string;
  icon?: ReactNode;
  tone?: MetricCardTone;
  sparkline?: number[];
  delta?: { value: number; percent: number; direction: "up" | "down" };
  animate?: boolean;
}) {
  const numericValue = typeof value === "number" ? value : NaN;
  const animatedValue = useCountUp(Number.isNaN(numericValue) ? 0 : numericValue, 600, animate && !Number.isNaN(numericValue));
  const displayValue = Number.isNaN(numericValue) ? value : animatedValue.toLocaleString("zh-CN");
  const styles = toneStyles[tone];

  return (
    <section
      className={`group panel panel-interactive relative min-h-[118px] overflow-hidden border-l-4 ${styles.border}`}
    >
      <div className={`absolute inset-x-0 top-0 h-1 overflow-hidden ${styles.accent}`}>
        <div className="h-full w-full opacity-0 transition-opacity duration-300 group-hover:opacity-100">
          <div className="accent-sheen h-full w-full bg-gradient-to-r from-transparent via-white/40 to-transparent" />
        </div>
      </div>
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{displayValue}</p>
          {delta ? (
            <div className="mt-1.5 flex items-center gap-1 text-xs">
              <span
                className={delta.direction === "up" ? "font-semibold text-emerald-600" : "font-semibold text-rose-500"}
              >
                {delta.direction === "up" ? "↑" : "↓"} {Math.abs(delta.value)}
              </span>
              <span className="font-medium text-slate-500">{delta.percent}%</span>
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-3">
          {icon ? <span className={`rounded-md p-2 ring-1 ${styles.icon}`}>{icon}</span> : null}
          {sparkline ? <Sparkline data={sparkline} tone={tone} /> : null}
        </div>
      </div>
      {description ? <p className="relative mt-1 text-xs leading-5 text-muted-foreground">{description}</p> : null}
    </section>
  );
}
