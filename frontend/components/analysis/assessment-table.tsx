"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import {
  listReportScopeItems,
  type ReportScopeFilters,
} from "@/lib/api";
import { reviewStatusLabels, riskLabels, verdictLabels } from "@/lib/business-labels";
import { PaginationControls } from "@/components/ui/pagination-controls";

const PAGE_SIZE = 50;

export function AssessmentTable({ reportId }: { reportId: string }) {
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [filters, setFilters] = useState<ReportScopeFilters>({});
  const query = useQuery({
    queryKey: [
      "report-scope-items",
      reportId,
      page,
      PAGE_SIZE,
      appliedQuery,
      filters.unitStatus,
      filters.effectiveVerdict,
      filters.reviewPriority,
      filters.reviewStatus,
      filters.applicabilityStatus,
    ],
    queryFn: () => listReportScopeItems(reportId, page, PAGE_SIZE, {
      ...filters,
      query: appliedQuery || undefined,
    }),
  });

  const hasFilters = Boolean(
    appliedQuery
    || filters.unitStatus
    || filters.effectiveVerdict
    || filters.reviewPriority
    || filters.reviewStatus
    || filters.applicabilityStatus,
  );
  function updateFilter<Key extends keyof ReportScopeFilters>(
    key: Key,
    value: ReportScopeFilters[Key] | undefined,
  ) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  }
  function clearFilters() {
    setPage(1);
    setSearchInput("");
    setAppliedQuery("");
    setFilters({});
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
        <div>
          <p className="text-sm font-semibold text-emerald-700">报告核查清单</p>
          <h1 className="mt-1 text-2xl font-semibold">完整 GRI 核查范围</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            独立判断项可进入人工复核；上下文条款已纳入相关判断，不重复生成结论。
          </p>
        </div>
        {query.data && (
          <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-800">共 {query.data.total} 项</span>
        )}
      </div>
      <div className="mt-4 space-y-3 rounded-xl border border-border bg-white p-4 shadow-sm">
        <form
          aria-label="核查范围搜索"
          className="flex flex-wrap items-end gap-2"
          role="search"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedQuery(searchInput.trim());
          }}
        >
          <label className="min-w-[240px] flex-1 text-xs font-medium text-slate-700">
            搜索核查范围
            <input
              className="mt-1 block h-10 w-full rounded-md border border-border px-3 text-sm"
              maxLength={100}
              placeholder="Requirement ID 或条款文本"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </label>
          <button className="h-10 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground" type="submit">
            搜索
          </button>
          <button className="h-10 rounded-md border border-border px-4 text-sm font-medium" type="button" onClick={clearFilters}>
            清空筛选
          </button>
        </form>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <label className="text-xs font-medium text-slate-700">
            单元类型
            <select className="mt-1 block h-10 w-full rounded-md border border-border px-2 text-sm" value={filters.unitStatus ?? ""} onChange={(event) => updateFilter("unitStatus", event.target.value ? event.target.value as ReportScopeFilters["unitStatus"] : undefined)}>
              <option value="">全部</option>
              <option value="assessed">独立判断项</option>
              <option value="context_incorporated">上下文项</option>
            </select>
          </label>
          <label className="text-xs font-medium text-slate-700">
            当前结论
            <select className="mt-1 block h-10 w-full rounded-md border border-border px-2 text-sm" value={filters.effectiveVerdict ?? ""} onChange={(event) => updateFilter("effectiveVerdict", event.target.value ? event.target.value as ReportScopeFilters["effectiveVerdict"] : undefined)}>
              <option value="">全部</option>
              <option value="disclosed">已披露</option>
              <option value="partially_disclosed">部分披露</option>
              <option value="omitted_with_reason">有理由省略</option>
              <option value="not_disclosed">未披露</option>
              <option value="unknown">待确认</option>
            </select>
          </label>
          <label className="text-xs font-medium text-slate-700">
            复核优先级
            <select className="mt-1 block h-10 w-full rounded-md border border-border px-2 text-sm" value={filters.reviewPriority ?? ""} onChange={(event) => updateFilter("reviewPriority", event.target.value ? event.target.value as ReportScopeFilters["reviewPriority"] : undefined)}>
              <option value="">全部</option>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </label>
          <label className="text-xs font-medium text-slate-700">
            复核状态
            <select className="mt-1 block h-10 w-full rounded-md border border-border px-2 text-sm" value={filters.reviewStatus ?? ""} onChange={(event) => updateFilter("reviewStatus", event.target.value ? event.target.value as ReportScopeFilters["reviewStatus"] : undefined)}>
              <option value="">全部</option>
              <option value="pending_review">待复核</option>
              <option value="reviewed_approved">已确认</option>
              <option value="reviewed_modified">已修改</option>
              <option value="evidence_invalidated">证据已作废</option>
              <option value="reopened">已重新打开</option>
            </select>
          </label>
          <label className="text-xs font-medium text-slate-700">
            适用性
            <select className="mt-1 block h-10 w-full rounded-md border border-border px-2 text-sm" value={filters.applicabilityStatus ?? ""} onChange={(event) => updateFilter("applicabilityStatus", event.target.value ? event.target.value as ReportScopeFilters["applicabilityStatus"] : undefined)}>
              <option value="">全部</option>
              <option value="applicable">适用</option>
              <option value="not_applicable">不适用</option>
              <option value="undetermined">待判定</option>
            </select>
          </label>
        </div>
      </div>
      {query.isLoading && <p className="p-6 text-sm text-muted-foreground">正在加载完整核查表...</p>}
      {query.isError && <p role="alert" className="p-6 text-sm text-red-700">完整 GRI 核查范围加载失败，请稍后重试。</p>}
      {query.data?.total === 0 && (
        <div className="mt-4 rounded-xl border border-dashed border-border bg-white p-8 text-center shadow-sm">
          <p className="text-sm text-muted-foreground">
            {hasFilters ? "当前筛选无匹配结果" : "当前报告暂无 GRI 核查范围"}
          </p>
        </div>
      )}
      {query.data && query.data.total > 0 && (
      <>
      <div className="mt-4 overflow-x-auto rounded-xl border border-border bg-white shadow-sm">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-100 text-xs text-slate-600">
            <tr>
              <th className="px-3 py-2">Requirement</th>
              <th className="px-3 py-2">主题</th>
              <th className="px-3 py-2">当前结论</th>
              <th className="px-3 py-2">复核优先级</th>
              <th className="px-3 py-2">复核状态</th>
              <th className="px-3 py-2">证据页</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {query.data.items.map((item) => {
              const isContext = item.unit_status === "context_incorporated";
              return (
                <tr key={item.requirement_id} className={isContext ? "bg-slate-50 text-muted-foreground" : "hover:bg-emerald-50/30"}>
                  <td className="px-3 py-3.5 font-medium">
                    {item.assessment_id ? (
                      <Link
                        className="text-accent underline-offset-4 hover:underline"
                        href={`/reports/${reportId}/review?assessmentId=${encodeURIComponent(item.assessment_id)}`}
                      >
                        {item.requirement_id}
                      </Link>
                    ) : item.requirement_id}
                  </td>
                  <td className="px-3 py-3.5">{item.gri_topic}</td>
                  <td className="px-3 py-3.5">
                    {isContext
                      ? "已纳入相关判断"
                      : verdictLabels[item.effective_verdict ?? ""] ?? item.effective_verdict ?? "-"}
                  </td>
                  <td className="px-3 py-3.5">
                    {isContext
                      ? "-"
                      : riskLabels[item.review_priority ?? ""] ?? item.review_priority ?? "-"}
                  </td>
                  <td className="px-3 py-3.5">
                    {isContext
                      ? "-"
                      : reviewStatusLabels[item.review_status ?? ""] ?? "待确认"}
                  </td>
                  <td className="px-3 py-3.5">{isContext ? "-" : item.source_pdf_pages.join(", ") || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <PaginationControls
        page={query.data.page}
        pageSize={query.data.page_size}
        total={query.data.total}
        unitLabel="项"
        onPageChange={setPage}
      />
      </>
      )}
    </div>
  );
}
