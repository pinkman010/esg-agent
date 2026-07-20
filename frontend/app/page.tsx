import { ArrowRight, Database, FileText, ShieldCheck } from "lucide-react";
import Link from "next/link";

const workflow = [
  { label: "上传报告", detail: "确认企业、年度和语言", icon: FileText },
  { label: "自动分析", detail: "核查 577 条 GRI 要求", icon: Database },
  { label: "人工复核", detail: "优先处理高优先级项目", icon: ShieldCheck },
];

export default function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-6">
      <section className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-muted-foreground">企业 ESG 核查工作台</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-foreground">GRI 披露核查</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
            从 ESG 报告列表进入上传、分析、复核、整改和输出流程。
          </p>
        </div>
        <Link
          href="/reports"
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground shadow-sm transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
        >
          打开报告列表
          <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {workflow.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="min-h-32 rounded-lg border border-border bg-white p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-muted text-accent">
                  <Icon aria-hidden="true" className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="text-base font-semibold tracking-normal">{item.label}</h2>
                  <p className="text-sm text-muted-foreground">{item.detail}</p>
                </div>
              </div>
            </div>
          );
        })}
      </section>

      <section className="rounded-lg border border-dashed border-border bg-white p-6">
        <h2 className="text-lg font-semibold tracking-normal">当前分析</h2>
        <p className="mt-2 text-sm text-muted-foreground">请从报告列表选择报告查看分析状态。</p>
      </section>
    </div>
  );
}
