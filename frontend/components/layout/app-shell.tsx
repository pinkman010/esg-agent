import type { ReactNode } from "react";

import { ClipboardCheck, FileText, History, Home, ListChecks } from "lucide-react";
import Link from "next/link";

const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/runs", label: "Runs", icon: ListChecks },
  { href: "/review", label: "Review", icon: ClipboardCheck },
  { href: "/audit", label: "Audit", icon: History },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex min-w-0 items-center gap-3" aria-label="ESG Agent home">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent text-sm font-semibold text-accent-foreground">
              EA
            </span>
            <span className="truncate text-sm font-semibold tracking-normal">ESG Agent</span>
          </Link>
          <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  <Icon aria-hidden="true" className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <div className="mx-auto grid w-full max-w-7xl grid-cols-1 md:grid-cols-[220px_1fr]">
        <aside className="hidden min-h-[calc(100vh-3.5rem)] border-r border-border bg-white px-3 py-4 md:block">
          <nav className="flex flex-col gap-1" aria-label="Section navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex h-10 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  <Icon aria-hidden="true" className="h-4 w-4" />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}