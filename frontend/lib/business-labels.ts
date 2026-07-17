export const verdictLabels: Record<string, string> = {
  disclosed: "已披露",
  partially_disclosed: "部分披露",
  unknown: "待确认",
  not_disclosed: "未披露",
};

export const riskLabels: Record<string, string> = { high: "高风险", medium: "中风险", low: "低风险" };

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
