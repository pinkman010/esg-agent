import type { AnalysisStageResponse } from "@/lib/types";

export const analysisStages = [
  ["file_validation", "文件检查"],
  ["pdf_parsing", "PDF 解析"],
  ["report_structure", "报告结构识别"],
  ["requirement_matching", "GRI requirement 匹配"],
  ["evidence_assessment", "证据与结论生成"],
  ["risk_classification", "复核优先级计算"],
  ["result_summary", "结果汇总"],
] as const;

export const analysisStageWeights = {
  file_validation: 5,
  pdf_parsing: 10,
  report_structure: 5,
  requirement_matching: 10,
  evidence_assessment: 60,
  risk_classification: 5,
  result_summary: 5,
} as const satisfies Record<(typeof analysisStages)[number][0], number>;

export function calculateAnalysisProgress(
  runStatus: string | undefined,
  stages: AnalysisStageResponse[],
): { percent: number; currentStageCode: string | null } {
  if (runStatus === "completed" || runStatus === "partially_completed") {
    return { percent: 100, currentStageCode: null };
  }

  const byCode = new Map(stages.map((stage) => [stage.stage_code, stage]));
  let weightedProgress = 0;
  let currentStageCode = analysisStages.find(([stageCode]) => byCode.get(stageCode)?.status === "running")?.[0] ?? null;

  for (const [stageCode] of analysisStages) {
    const stage = byCode.get(stageCode);
    if (!stage) continue;
    const weight = analysisStageWeights[stageCode];
    if (stage?.status === "completed" || stage?.status === "partially_failed") {
      weightedProgress += weight;
      continue;
    }
    if ((stage.status === "running" || stage.status === "failed") && stage.total_units > 0) {
      const fraction = Math.min(1, Math.max(0, stage.completed_units / stage.total_units));
      weightedProgress += weight * fraction;
    }
  }

  if (!currentStageCode) {
    currentStageCode = analysisStages.find(([stageCode]) => {
      const status = byCode.get(stageCode)?.status;
      return status === "failed" || status === "partially_failed";
    })?.[0] ?? null;
  }

  const percent = Math.floor(weightedProgress);
  return { percent: Math.min(100, Math.max(0, percent)), currentStageCode };
}

export function isAnalysisProgressStalled(
  runStatus: string | undefined,
  stages: AnalysisStageResponse[],
  now = new Date(),
  staleAfterMs = 120_000,
): boolean {
  if (runStatus !== "running") return false;
  const latestEventTime = stages.reduce((latest, stage) => {
    if (!stage.created_at) return latest;
    const timestamp = Date.parse(stage.created_at);
    return Number.isFinite(timestamp) ? Math.max(latest, timestamp) : latest;
  }, Number.NEGATIVE_INFINITY);
  if (!Number.isFinite(latestEventTime)) return false;
  return now.getTime() - latestEventTime > staleAfterMs;
}
