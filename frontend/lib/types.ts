import type { components } from "./generated/api-types";

export type RunStatus = components["schemas"]["RunStatus"];
export type ReviewStatus = components["schemas"]["ReviewStatus"];
export type AssessmentVerdict = components["schemas"]["AssessmentVerdict"];
export type ReportUploadResponse = components["schemas"]["ReportUploadResponse"];
export type ReportResponse = components["schemas"]["ReportResponse"];
export type ReportListResponse = components["schemas"]["ReportListResponse"];
export type DuplicateReportDetail = {
  code: "duplicate_report";
  message: string;
  report_id: string;
  existing_report_status: ReportResponse["status"];
  can_start_new_demo: boolean;
};
export type DemoResetResponse = {
  cleared_report_count: number;
  cleared_runtime_directories: Array<"uploads" | "derived">;
};
export type ConfirmReportMetadataRequest = components["schemas"]["ConfirmReportMetadataRequest"];
export type AnalyzeResponse = components["schemas"]["AnalyzeResponse"];
export type AnalysisRun = components["schemas"]["AnalysisRun"];
export type AnalysisStageResponse = components["schemas"]["AnalysisStageResponse"];
export type AssessmentListItem = components["schemas"]["AssessmentListItem"];
export type AssessmentListResponse = components["schemas"]["AssessmentListResponse"];
export type ReportDashboardResponse = components["schemas"]["ReportDashboardResponse"];
export type ReviewSnapshot = components["schemas"]["ReviewSnapshot"];
export type ReviewSnapshotRequest = components["schemas"]["ReviewSnapshotRequest"];
export type AssessmentDetailResponse = components["schemas"]["AssessmentDetailResponse"];
export type ImprovementAction = components["schemas"]["ImprovementAction"];
export type ExportVersion = components["schemas"]["ExportVersion"];
export type EvidenceItem = components["schemas"]["EvidenceItem"];
export type DisclosureAssessment = components["schemas"]["DisclosureAssessment"];
export type Recommendation = components["schemas"]["Recommendation"];
export type ReviewDecisionRequest = components["schemas"]["ReviewDecisionRequest"];
export type ReviewDecision = components["schemas"]["ReviewDecision"];
export type AuditEvent = components["schemas"]["AuditEvent"];
export type AuditRun = components["schemas"]["AuditRun"];
