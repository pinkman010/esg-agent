"use client";

import { RotateCcw, SearchX } from "lucide-react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  onReset?: () => void;
  resetLabel?: string;
  variant?: "search" | "data" | "filter";
}

function EmptyIllustration({ variant }: { variant: EmptyStateProps["variant"] }) {
  if (variant === "search") {
    return (
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 ring-1 ring-emerald-100">
        <SearchX className="h-8 w-8 text-emerald-500" />
      </div>
    );
  }

  if (variant === "filter") {
    return (
      <svg width="64" height="64" viewBox="0 0 64 64" fill="none" className="text-emerald-500">
        <rect x="8" y="12" width="48" height="6" rx="3" className="fill-emerald-100" />
        <rect x="14" y="24" width="36" height="6" rx="3" className="fill-emerald-100" />
        <rect x="20" y="36" width="24" height="6" rx="3" className="fill-emerald-100" />
        <circle cx="48" cy="44" r="12" className="fill-emerald-50 stroke-emerald-200" strokeWidth="2" />
        <path d="M44 44h8M48 40v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }

  // data
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" className="text-emerald-500">
      <rect x="10" y="8" width="44" height="48" rx="6" className="fill-emerald-50 stroke-emerald-100" strokeWidth="2" />
      <rect x="18" y="18" width="28" height="4" rx="2" className="fill-emerald-100" />
      <rect x="18" y="28" width="20" height="4" rx="2" className="fill-emerald-100" />
      <rect x="18" y="38" width="24" height="4" rx="2" className="fill-emerald-100" />
      <circle cx="46" cy="48" r="10" className="fill-white stroke-emerald-200" strokeWidth="2" />
      <path d="M42 48h8M46 44v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function EmptyState({
  title = "暂无匹配结果",
  description = "请尝试调整筛选条件",
  onReset,
  resetLabel = "重置筛选条件",
  variant = "filter",
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/80 p-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 ring-1 ring-emerald-100 transition-transform duration-300 hover:scale-105">
        <EmptyIllustration variant={variant} />
      </div>
      <p className="mt-4 text-sm font-semibold text-slate-700">{title}</p>
      <p className="mt-1 text-xs text-slate-400">{description}</p>
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:bg-emerald-50/60 hover:text-emerald-700 hover:shadow-md active:translate-y-0"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          {resetLabel}
        </button>
      )}
    </div>
  );
}
