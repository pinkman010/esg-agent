"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CircleHelp,
  FileCheck2,
  FileOutput,
  ListChecks,
  Scale,
  UserCheck,
} from "lucide-react";
import Link from "next/link";

import { ReportPageHero } from "@/components/layout/report-page-hero";
import { MetricCard } from "@/components/ui/metric-card";
import { Skeleton, SkeletonCard, SkeletonMetricCard } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { buttonVariants } from "@/components/ui/button";
import { getReportDashboard, getRun } from "@/lib/api";
import { DashboardDistribution } from "./dashboard-distribution";
import { VerdictDistributionPie } from "./verdict-distribution-pie";
import { WorkloadRadarChart } from "./workload-radar-chart";

export function ReportDashboard({ reportId }: { reportId: string }) {
  const query = useQuery({ queryKey: ["report-dashboard", reportId], queryFn: () => getReportDashboard(reportId) });
  const runQuery = useQuery({
    queryKey: ["run", query.data?.run_id],
    queryFn: () => getRun(query.data?.run_id ?? ""),
    enabled: Boolean(query.data?.run_id),
  });
  if (query.isLoading) {
    return (
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-6 lg:px-7" aria-label="报告总览加载中">
        <div className="panel space-y-4 p-6">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SkeletonMetricCard />
          <SkeletonMetricCard />
          <SkeletonMetricCard />
          <SkeletonMetricCard />
        </div>
        <SkeletonCard />
      </div>
    );
  }
  if (query.isError || !query.data) {
    return <p role="alert" className="p-6 text-sm text-red-700">报告总览加载失败，请稍后重试。</p>;
  }
  const data = query.data;
  const priorities = data.review_priority_counts ?? data.risk_counts;
  const analysisIncomplete = data.analysis_incomplete_count ?? data.failed_requirement_count;
  const notGenerated = data.not_generated_requirement_count ?? 0;
  const formalBlocked = analysisIncomplete > 0 || data.high_priority_unresolved > 0;
  const aiStatus = runQuery.isLoading
    ? "正在读取 AI 阶段状态"
    : runQuery.isError
      ? "AI 阶段状态读取失败"
      : runQuery.data?.confirm_llm
        ? `AI 建议成功 ${runQuery.data.ai_summary.succeeded} 项，失败 ${runQuery.data.ai_summary.failed} 项`
        : "本次分析未启用 AI 辅助";

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="当前报告"
        title="报告总览"
        imageSrc="/visuals/module-policy-disclosure.webp"
        imagePosition="28% 50%"
        animated
        meta={(
          <>
            <StatusBadge tone="success">核查范围 {data.standard_unit_count} 项</StatusBadge>
            <StatusBadge tone={data.high_priority_unresolved > 0 ? "danger" : "success"}>
              高优先级复核 {data.high_priority_reviewed}/{data.high_priority_total}
            </StatusBadge>
          </>
        )}
        description="高优先级复核完成不代表全部 577 项均已人工确认。"
        action={(
          <Link href={`/reports/${reportId}/review`} className={buttonVariants()}>
            <ListChecks aria-hidden="true" className="h-4 w-4" />
            进入复核工作台
          </Link>
        )}
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="报告核查指标">
        <MetricCard
          label="高优先级未解决"
          value={data.high_priority_unresolved}
          description={`高优先级共 ${data.high_priority_total} 项`}
          tone="danger"
          icon={<AlertTriangle aria-hidden="true" className="h-4 w-4" />}
        />
        <MetricCard
          label="复核进度"
          value={`${data.high_priority_reviewed}/${data.high_priority_total}`}
          description="仅覆盖高优先级队列"
          tone="success"
          icon={<UserCheck aria-hidden="true" className="h-4 w-4" />}
        />
        <MetricCard
          label="适用性待判定"
          value={data.applicability_undetermined_total}
          description="需要企业条件判断"
          tone="info"
          icon={<CircleHelp aria-hidden="true" className="h-4 w-4" />}
        />
        <MetricCard
          label="分析不完整"
          value={analysisIncomplete}
          description={analysisIncomplete > 0 ? `失败 ${data.failed_requirement_count}，未生成 ${notGenerated}` : "当前分析完整"}
          tone={analysisIncomplete > 0 ? "danger" : "neutral"}
          icon={<FileCheck2 aria-hidden="true" className="h-4 w-4" />}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <DashboardDistribution
          title="披露结论"
          description="当前独立判断结果；上下文条款不重复计入"
          counts={data.verdict_counts}
          items={[
            { key: "disclosed", label: "已披露", tone: "success" },
            { key: "partially_disclosed", label: "部分披露", tone: "warning" },
            { key: "not_disclosed", label: "未披露", tone: "danger" },
            { key: "unknown", label: "待确认", tone: "neutral" },
          ]}
        />
        <DashboardDistribution
          title="复核优先级"
          description="当前独立判断结果；用于安排人工处理顺序"
          counts={priorities}
          items={[
            { key: "high", label: "高优先级", tone: "danger" },
            { key: "medium", label: "中优先级", tone: "warning" },
            { key: "low", label: "低优先级", tone: "success" },
          ]}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2" aria-label="核查分布图表">
        <VerdictDistributionPie counts={data.verdict_counts} />
        <WorkloadRadarChart
          priorities={priorities}
          applicabilityUndetermined={data.applicability_undetermined_total}
          analysisIncomplete={analysisIncomplete}
        />
      </section>

      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">判断分层</h2>
          <span className="text-xs text-muted-foreground">规则、AI、人工分别留痕</span>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <div className="rounded-lg border border-border p-4">
            <Scale aria-hidden="true" className="h-5 w-5 text-emerald-700" />
            <h3 className="mt-3 text-sm font-semibold">规则分析</h3>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">确定性规则结果已生成，原始系统字段保持不可变。</p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <Bot aria-hidden="true" className="h-5 w-5 text-sky-700" />
            <h3 className="mt-3 text-sm font-semibold">AI 辅助</h3>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{aiStatus}</p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <UserCheck aria-hidden="true" className="h-5 w-5 text-amber-700" />
            <h3 className="mt-3 text-sm font-semibold">人工复核</h3>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              高优先级已复核 {data.high_priority_reviewed}/{data.high_priority_total}，每次操作追加保存快照。
            </p>
          </div>
        </div>
      </section>

      <section className={`rounded-xl border p-5 ${formalBlocked ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-semibold">正式输出门禁</h2>
            {analysisIncomplete > 0 ? (
              <p className="mt-2 text-sm text-red-700">其中 {analysisIncomplete} 条分析失败或未生成结果，需重跑后才能正式输出。</p>
            ) : data.high_priority_unresolved > 0 ? (
              <p className="mt-2 text-sm text-amber-900">高优先级未解决 {data.high_priority_unresolved} 项</p>
            ) : (
              <p className="mt-2 text-sm text-emerald-800">分析完整且高优先级队列已完成，可申请正式输出。</p>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              草稿始终披露中优先级、低优先级和适用性待判定范围。
            </p>
          </div>
          <Link
            href={`/reports/${reportId}/exports`}
            className={buttonVariants({ variant: "secondary" })}
          >
            <FileOutput aria-hidden="true" className="h-4 w-4" />
            查看输出与版本
          </Link>
        </div>
      </section>

      <nav className="grid gap-3 sm:grid-cols-2" aria-label="报告后续操作">
        <Link href={`/reports/${reportId}/assessments`} className="panel panel-interactive flex items-center justify-between p-4 text-sm font-semibold">
          查看完整 GRI 核查表
          <ArrowRight aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
        </Link>
        <Link href={`/reports/${reportId}/actions`} className="panel panel-interactive flex items-center justify-between p-4 text-sm font-semibold">
          查看整改任务
          <ArrowRight aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
        </Link>
      </nav>
    </div>
  );
}
