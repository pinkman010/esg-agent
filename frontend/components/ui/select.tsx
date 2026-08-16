"use client";

import { useId } from "react";
import { ChevronDown } from "lucide-react";
import clsx from "clsx";

interface SelectProps<T extends string> {
  label: string;
  value: T;
  options: T[];
  onChange: (value: T) => void;
  format?: (value: T) => string;
  compact?: boolean;
}

export function Select<T extends string>({
  label,
  value,
  options,
  onChange,
  format,
  compact = false,
}: SelectProps<T>) {
  const selectId = useId();

  return (
    <div className={clsx("relative", compact ? "min-w-[130px]" : "min-w-[150px]")}>
      <label
        htmlFor={selectId}
        className={clsx("block text-xs font-semibold text-slate-500", compact ? "mb-1" : "mb-2")}
      >
        {label}
      </label>
      <div className="relative">
        <select
          id={selectId}
          value={value}
          onChange={(event) => onChange(event.target.value as T)}
          className={clsx(
            "w-full appearance-none rounded border border-slate-200 bg-white pr-9 text-sm text-slate-700 outline-none transition",
            "hover:border-emerald-300 hover:shadow-sm focus:border-emerald-400 focus:shadow-md focus:ring-1 focus:ring-emerald-100",
            compact ? "px-2.5 py-1.5" : "px-3 py-2",
          )}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {format ? format(option) : option === "all" ? "全部" : option}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
        />
      </div>
    </div>
  );
}
