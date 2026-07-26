import type { ReactNode } from "react";

const toneClasses = {
  neutral: "border-l-slate-400",
  danger: "border-l-red-500",
  warning: "border-l-amber-500",
  success: "border-l-emerald-600",
  info: "border-l-sky-500",
} as const;

export function MetricCard({
  label,
  value,
  description,
  icon,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  description?: string;
  icon?: ReactNode;
  tone?: keyof typeof toneClasses;
}) {
  return (
    <section className={`rounded-xl border border-border border-l-4 bg-white p-4 shadow-sm ${toneClasses[tone]}`}>
      <div className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
        <span>{label}</span>
        {icon}
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{value}</p>
      {description && <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>}
    </section>
  );
}
