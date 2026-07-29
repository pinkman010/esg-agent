"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, listReportAudit } from "@/lib/api";

const PAGE_SIZE = 20;
const eventLabels: Record<string, string> = {
  report_uploaded: "报告已上传",
  report_metadata_confirmed: "报告信息已确认",
  report_profile_resolved: "报告画像已匹配",
  analysis_started: "分析已启动",
  parse_completed: "PDF 解析已完成",
  analysis_completed: "分析已完成",
  analysis_failed: "分析执行失败",
  analysis_interrupted_by_restart: "分析因服务重启中断",
  requirement_analysis_failed: "核查项分析失败",
  analysis_retry_created: "失败项目重跑已创建",
  review_decision_saved: "复核决定已保存",
  review_snapshot_created: "人工复核快照已保存",
  applicability_batch_reviewed: "适用性批量复核已保存",
  improvement_action_created: "整改任务已创建",
  improvement_action_updated: "整改任务已更新",
  export_generated: "输出版本已生成",
  draft_export_created: "草稿输出已生成",
  formal_export_created: "正式输出已生成",
  export_file_downloaded: "输出文件已下载",
  assessments_json_exported: "核查结果 JSON 已导出",
  assessments_csv_exported: "核查结果 CSV 已导出",
  review_json_exported: "复核结果 JSON 已导出",
  review_csv_exported: "复核结果 CSV 已导出",
};
const payloadLabels: Record<string, string> = {
  report_id: "报告",
  parent_run_id: "原运行",
  retry_run_id: "重跑运行",
  retry_requirement_count: "重跑项目数",
  failed_requirement_ids: "失败核查项",
  assessment_count: "核查项数",
  assessment_id: "核查项",
  requirement_id: "核查项",
  action_id: "整改任务",
  export_id: "输出版本",
  supersedes_export_id: "替代的输出版本",
  version_number: "版本号",
  snapshot_id: "快照",
  sequence: "快照序号",
  operation_type: "操作类型",
  profile_id: "报告画像",
  matched: "画像匹配",
  confirm_llm: "启用外部模型",
  formats: "输出格式",
  format: "文件格式",
  file_id: "文件",
  size: "文件大小（字节）",
  sha256: "文件校验值",
  page_count: "PDF 页数",
  chunk_count: "文本块数",
  digital_text_page_count: "数字文本页数",
  low_text_density_page_count: "低文本密度页数",
  scanned_page_count: "扫描页数",
  document_capability: "文档处理能力",
  old_status: "原状态",
  new_status: "新状态",
  changed_fields: "变更字段",
  row_count: "导出行数",
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

function auditErrorMessage(error: unknown): string {
  if (
    error instanceof ApiError
    && error.status === 404
    && typeof error.body === "object"
    && error.body !== null
    && "detail" in error.body
    && error.body.detail === "Not Found"
  ) {
    return "当前服务版本与页面不一致，请重启后端服务后重试。";
  }
  return "报告审计记录加载失败，请稍后重试。";
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
    return <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">{auditErrorMessage(query.error)}</p>;
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
