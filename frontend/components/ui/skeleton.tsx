import clsx from "clsx";

interface SkeletonProps {
  className?: string;
  variant?: "rect" | "circle" | "text";
}

export function Skeleton({ className = "", variant = "rect" }: SkeletonProps) {
  return (
    <div
      className={clsx(
        "animate-shimmer",
        variant === "circle" && "rounded-full",
        variant === "rect" && "rounded-md",
        variant === "text" && "rounded",
        className,
      )}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="panel space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-1 rounded-full" />
          <Skeleton className="h-4 w-32" />
        </div>
        <Skeleton className="h-8 w-20" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-4 gap-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonMetricCard() {
  return (
    <div className="panel min-h-[118px] space-y-3 border border-slate-200/60">
      <div className="flex items-start justify-between">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-3 w-24" />
        </div>
        <Skeleton variant="circle" className="h-9 w-9" />
      </div>
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={`th-${i}`} className="h-8 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={`tr-${i}`} className="flex gap-2">
          {Array.from({ length: 6 }).map((_, j) => (
            <Skeleton key={`td-${i}-${j}`} className="h-10 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}
