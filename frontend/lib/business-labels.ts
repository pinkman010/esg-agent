export const reportStatusLabels: Record<string, string> = {
  uploaded: "待确认报告信息",
  metadata_detected: "待确认报告信息",
  awaiting_confirmation: "待确认报告信息",
  ready_for_analysis: "待启动分析",
  analyzing: "分析中",
  analysis_completed: "分析已完成",
  partially_completed: "分析部分完成",
  analysis_failed: "分析失败",
  high_risk_review_completed: "高优先级复核已完成",
  formally_exported: "已生成正式输出",
  reopened: "已重新开启",
  archived: "已归档",
};

export const verdictLabels: Record<string, string> = {
  disclosed: "已披露",
  partially_disclosed: "部分披露",
  unknown: "待确认",
  not_disclosed: "未披露",
};

export const reviewPriorityLabels: Record<string, string> = {
  high: "高优先级",
  medium: "中优先级",
  low: "低优先级",
};

export const riskLabels = reviewPriorityLabels;

export const evidenceStatusLabels: Record<string, string> = {
  valid_direct: "直接有效证据",
  missing: "缺少有效证据",
  non_substantive_only: "仅有索引或从略说明",
  quality_warning: "证据质量待确认",
  invalid: "证据无效",
  conflict: "存在冲突",
};

export const applicabilityStatusLabels: Record<string, string> = {
  applicable: "适用",
  not_applicable_claimed: "企业声称不适用",
  not_applicable_confirmed: "人工确认不适用",
  undetermined: "待判定",
};

export const reviewStatusLabels: Record<string, string> = {
  pending_review: "待复核",
  reviewed_approved: "已通过",
  reviewed_modified: "已修改",
  evidence_invalidated: "证据无效",
  reopened: "已重新开启",
  not_required: "无需复核",
  needs_manual_review: "需要人工复核",
  approved: "已通过",
  rejected: "已驳回",
  corrected: "已修正",
};
