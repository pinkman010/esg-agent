import clsx from "clsx";

const toneClasses = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  danger: "bg-red-50 text-red-700 ring-red-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  info: "bg-sky-50 text-sky-700 ring-sky-200",
} as const;

export type StatusBadgeTone = keyof typeof toneClasses;

export function StatusBadge({
  children,
  tone = "neutral",
  variant = "soft",
}: {
  children: React.ReactNode;
  tone?: StatusBadgeTone;
  /** soft：纯色徽章（默认，兼容旧用法）；outline：带 ring 描边（来自 esg-dashboard Badge 体系） */
  variant?: "soft" | "outline";
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2.5 py-1 text-xs font-medium",
        variant === "outline" ? "rounded ring-1 font-semibold" : "rounded-full",
        toneClasses[tone],
      )}
    >
      {children}
    </span>
  );
}
