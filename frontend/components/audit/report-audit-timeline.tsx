"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listReportAudit } from "@/lib/api";

const PAGE_SIZE = 20;
const eventLabels: Record<string, string> = {
  report_uploaded: "报告已上传",
  report_metadata_confirmed: "报告信息已确认",
  parse_completed: "PDF 解析已完成",
  analysis_completed: "分析已完成",
  analysis_failed: "分析执行失败",
  analysis_interrupted_by_restart: "分析因服务重启中断",
  requirement_analysis_failed: "核查项分析失败",
  analysis_retry_created: "失败项目重跑已创建",
  review_decision_saved: "复核决定已保存",
  applicability_batch_reviewed: "适用性批量复核已保存",
  improvement_action_created: "整改任务已创建",
  improvement_action_updated: "整改任务已更新",
  export_generated: "输出版本已生成",
  export_file_downloaded: "输出文件已下载",
};
const payloadLabels: Record<string, string> = {
  report_id: "报告",
  parent_run_id: "原运行",
  retry_run_id: "重跑运行",
  retry_requirement_count: "重跑项目数",
  failed_requirement_ids: "失败 Requirement",
  assessment_count: "核查项数",
  action_id: "整改任务",
  export_id: "输出版本",
  error_code: "错误代码",
  error: "错误说明",
  reason: "原因",
};

function payloadValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(payloadValue).join("、");
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return "详细信息已记录";
  return String(value);
}

export function ReportAuditTimeline({ reportId }: { reportId: string }) {
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["report-audit", reportId, offset, PAGE_SIZE],
    queryFn: () => listReportAudit(reportId, offset, PAGE_SIZE),
  });

  if (query.isLoading) {
    return <p className="rounded-xl border border-border bg-white p-5 text-sm text-muted-foreground">正在加载报告审计记录...</p>;
  }
  if (query.isError || !query.data) {
    return <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">报告审计记录加载失败，请稍后重试。</p>;
  }
  const data = query.data;
  return (
    <section>
      <header className="border-b border-border pb-5">
        <p className="text-sm font-semibold text-emerald-700">报告留痕</p>
        <h1 className="mt-1 text-2xl font-semibold">审计时间线</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          汇总报告上传、分析、重跑、人工复核、整改和输出事件。技术敏感信息已从公开视图移除。
        </p>
      </header>

      {data.items.length === 0 ? (
        <p className="mt-5 rounded-xl border border-dashed border-border bg-white p-8 text-center text-sm text-muted-foreground">
          当前报告暂无审计事件
        </p>
      ) : (
        <ol className="mt-5 space-y-3">
          {data.items.map((event) => (
            <li key={event.audit_event_id} className="rounded-xl border border-border bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold">
                    {eventLabels[event.event_type] ?? "系统事件"}
                  </h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {event.run_id ? `运行 ${event.run_id}` : "报告级事件"}
                  </p>
                </div>
                <time className="text-xs text-muted-foreground" dateTime={event.created_at ?? undefined}>
                  {event.created_at
                    ? new Date(event.created_at).toLocaleString("zh-CN")
                    : "时间待记录"}
                </time>
              </div>
              {Object.keys(event.payload).length > 0 && (
                <dl className="mt-3 grid gap-2 rounded-lg bg-slate-50 p-3 text-xs sm:grid-cols-2">
                  {Object.entries(event.payload).map(([key, value]) => (
                    <div key={key}>
                      <dt className="text-muted-foreground">
                        {payloadLabels[key] ?? key}
                      </dt>
                      <dd className="mt-1 break-words font-medium">
                        {payloadValue(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </li>
          ))}
        </ol>
      )}

      <div className="mt-5 flex items-center justify-between gap-3 text-sm">
        <span className="text-muted-foreground">
          共 {data.total} 条
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border border-border bg-white px-3 py-2 font-medium disabled:opacity-40"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            上一页
          </button>
          <button
            type="button"
            className="rounded-md border border-border bg-white px-3 py-2 font-medium disabled:opacity-40"
            disabled={offset + PAGE_SIZE >= data.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            下一页
          </button>
        </div>
      </div>
    </section>
  );
}
