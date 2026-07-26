type Tone = "neutral" | "danger" | "warning" | "success" | "info";

const barClasses: Record<Tone, string> = {
  neutral: "bg-slate-500",
  danger: "bg-red-500",
  warning: "bg-amber-500",
  success: "bg-emerald-600",
  info: "bg-sky-500",
};

export function DashboardDistribution({
  title,
  description,
  counts,
  items,
}: {
  title: string;
  description: string;
  counts: Record<string, number>;
  items: Array<{ key: string; label: string; tone: Tone }>;
}) {
  const total = items.reduce((sum, item) => sum + (counts[item.key] ?? 0), 0);

  return (
    <section className="rounded-xl border border-border bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
      {total === 0 ? (
        <p className="mt-6 rounded-lg bg-muted/60 p-4 text-sm text-muted-foreground">暂无可汇总结果</p>
      ) : (
        <div className="mt-5 space-y-4">
          {items.map((item) => {
            const count = counts[item.key] ?? 0;
            const percent = (count / total) * 100;
            return (
              <div key={item.key}>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium">{item.label}</span>
                  <span className="flex items-baseline gap-2">
                    <strong className="text-base">{count}</strong>
                    <span className="text-xs text-muted-foreground">{percent.toFixed(1)}%</span>
                  </span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full ${barClasses[item.tone]}`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
