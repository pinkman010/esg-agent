import type { ReactNode } from "react";

import { FileText, Home } from "lucide-react";
import Link from "next/link";

import { ReportContextNav } from "./report-context-nav";

const mobileNavItems = [
  { href: "/", label: "工作台首页", icon: Home },
  { href: "/reports", label: "ESG 报告", icon: FileText },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-[1800px] items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex min-w-0 items-center gap-3" aria-label="ESG Agent 首页">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-sm font-semibold text-accent-foreground shadow-sm">
              EA
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold tracking-normal">ESG Agent</span>
              <span className="hidden text-[11px] text-muted-foreground sm:block">GRI 核查工作台</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1 md:hidden" aria-label="移动端主导航">
            {mobileNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="inline-flex h-9 items-center gap-2 rounded-md px-2 text-xs text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                >
                  <Icon aria-hidden="true" className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <div className="mx-auto grid w-full max-w-[1800px] grid-cols-1 md:grid-cols-[236px_minmax(0,1fr)]">
        <aside className="hidden min-h-[calc(100vh-4rem)] border-r border-border bg-white px-3 py-5 md:block">
          <ReportContextNav />
        </aside>
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
