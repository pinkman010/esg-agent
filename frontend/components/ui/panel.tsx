"use client";

import { useId, useState } from "react";
import { Info } from "lucide-react";

export function Panel({
  title,
  action,
  children,
  className = "",
  contentClassName,
  showInfo = false,
  infoTip,
}: {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  showInfo?: boolean;
  infoTip?: string;
}) {
  const [tipVisible, setTipVisible] = useState(false);
  const tooltipId = useId();

  return (
    <section className={`panel ${className}`}>
      {title ? (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="h-4 w-1 rounded-full bg-gradient-to-b from-emerald-500 to-emerald-300 shadow-[0_0_6px_rgba(16,185,129,0.25)]" />
            <h2 className="text-base font-semibold tracking-tight text-slate-950">{title}</h2>
            {showInfo ? (
              <div
                className="relative"
                onMouseEnter={() => setTipVisible(true)}
                onMouseLeave={() => setTipVisible(false)}
                onFocus={() => setTipVisible(true)}
                onBlur={() => setTipVisible(false)}
              >
                <button
                  type="button"
                  className="cursor-help rounded text-slate-400 transition-colors hover:text-emerald-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
                  aria-label={`查看${title}说明`}
                  aria-controls={infoTip ? tooltipId : undefined}
                  aria-expanded={Boolean(infoTip && tipVisible)}
                  onClick={() => setTipVisible((visible) => !visible)}
                >
                  <Info aria-hidden="true" className="h-4 w-4" />
                </button>
                {infoTip && tipVisible && (
                  <div
                    id={tooltipId}
                    className="absolute left-1/2 top-full z-50 mt-2 w-56 -translate-x-1/2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-600 shadow-lg"
                    role="tooltip"
                  >
                    <span className="absolute -top-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-l border-t border-slate-200 bg-white" />
                    {infoTip}
                  </div>
                )}
              </div>
            ) : null}
          </div>
          {action}
        </div>
      ) : null}
      {contentClassName ? <div className={contentClassName}>{children}</div> : children}
    </section>
  );
}
