import type {
  AnalysisRun,
  AnalysisStageResponse,
  AssessmentListResponse,
  AssessmentDetailResponse,
  ReportDashboardResponse,
  ImprovementAction,
  ExportVersion,
  AnalyzeResponse,
  AuditRun,
  ConfirmReportMetadataRequest,
  DisclosureAssessment,
  Recommendation,
  ReportListResponse,
  ReportResponse,
  ReviewSnapshot,
  ReviewSnapshotRequest,
  ReportUploadResponse,
  ReviewDecision,
  ReviewDecisionRequest,
} from "./types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

type RequestOptions = Omit<RequestInit, "body"> & { body?: BodyInit | object };

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, body: unknown) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseResponse(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  const inputBody = options.body;
  let body: BodyInit | undefined;
  if (inputBody && !(inputBody instanceof FormData) && typeof inputBody !== "string") {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(inputBody);
  } else {
    body = inputBody as BodyInit | undefined;
  }
  const response = await fetch(apiUrl(path), { ...options, headers, body });
  const parsed = await parseResponse(response);
  if (!response.ok) throw new ApiError(response.status, parsed);
  return parsed as T;
}

export function uploadReport(file: File): Promise<ReportUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<ReportUploadResponse>("/api/reports/upload", { method: "POST", body: formData });
}
export function listReports(page = 1, pageSize = 50): Promise<ReportListResponse> {
  return request<ReportListResponse>(`/api/reports?page=${page}&page_size=${pageSize}`);
}
export function getReport(reportId: string): Promise<ReportResponse> {
  return request<ReportResponse>(`/api/reports/${reportId}`);
}
export function confirmReportMetadata(reportId: string, payload: ConfirmReportMetadataRequest): Promise<ReportResponse> {
  return request<ReportResponse>(`/api/reports/${reportId}/confirm-metadata`, { method: "POST", body: payload });
}
export function analyzeReport(reportId: string, confirmLlm: boolean): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(`/api/reports/${reportId}/analyze`, { method: "POST", body: { confirm_llm: confirmLlm } });
}
export function listRuns(): Promise<AnalysisRun[]> { return request<AnalysisRun[]>("/api/runs"); }
export function getRun(runId: string): Promise<AnalysisRun> { return request<AnalysisRun>(`/api/runs/${runId}`); }
export function getRunStages(runId: string): Promise<AnalysisStageResponse[]> { return request<AnalysisStageResponse[]>(`/api/runs/${runId}/stages`); }
export function retryFailedRun(runId: string, reason: string): Promise<AnalysisRun> {
  return request<AnalysisRun>(`/api/runs/${runId}/retry-failed`, { method: "POST", body: { reason } });
}
export function getReviewQueue(reportId: string): Promise<AssessmentListResponse> {
  return request<AssessmentListResponse>(`/api/reports/${reportId}/review-queue`);
}
export function listReportAssessments(reportId: string, page = 1): Promise<AssessmentListResponse> {
  return request<AssessmentListResponse>(`/api/reports/${reportId}/assessments?page=${page}&page_size=50`);
}
export function saveReviewSnapshot(assessmentId: string, payload: ReviewSnapshotRequest): Promise<ReviewSnapshot> {
  return request<ReviewSnapshot>(`/api/assessments/${assessmentId}/review-decisions`, { method: "POST", body: payload });
}
export function getReviewHistory(assessmentId: string): Promise<ReviewSnapshot[]> {
  return request<ReviewSnapshot[]>(`/api/assessments/${assessmentId}/review-history`);
}
export function getAssessmentDetail(reportId: string, assessmentId: string): Promise<AssessmentDetailResponse> {
  return request<AssessmentDetailResponse>(`/api/reports/${reportId}/assessments/${assessmentId}`);
}
export function getReportDashboard(reportId: string): Promise<ReportDashboardResponse> {
  return request<ReportDashboardResponse>(`/api/reports/${reportId}/dashboard`);
}
export function listActions(reportId: string): Promise<ImprovementAction[]> {
  return request<ImprovementAction[]>(`/api/reports/${reportId}/actions`);
}
export function listExportVersions(reportId: string): Promise<ExportVersion[]> {
  return request<ExportVersion[]>(`/api/reports/${reportId}/exports`);
}
export function generateExport(reportId: string, isDraft: boolean, createdBy: string): Promise<ExportVersion> {
  return request<ExportVersion>(`/api/reports/${reportId}/exports/${isDraft ? "draft" : "formal"}`, { method: "POST", body: { formats: ["assessment_xlsx", "management_pdf", "actions_xlsx", "print_html"], created_by: createdBy } });
}
export function listRunAssessments(runId: string): Promise<DisclosureAssessment[]> { return request<DisclosureAssessment[]>(`/api/runs/${runId}/assessments`); }
export function listRunRecommendations(runId: string): Promise<Recommendation[]> { return request<Recommendation[]>(`/api/runs/${runId}/recommendations`); }
export function listReviewRuns(): Promise<AnalysisRun[]> { return request<AnalysisRun[]>("/api/review/runs"); }
export function listReviewAssessments(runId: string): Promise<DisclosureAssessment[]> { return request<DisclosureAssessment[]>(`/api/review/runs/${runId}/assessments`); }
export function saveReviewDecision(runId: string, decision: ReviewDecisionRequest): Promise<ReviewDecision> {
  return request<ReviewDecision>(`/api/review/runs/${runId}/decisions`, { method: "POST", body: decision });
}
export function exportAssessmentsJson(runId: string): Promise<Record<string, unknown>[]> { return request<Record<string, unknown>[]>(`/api/exports/runs/${runId}/assessments.json`); }
export function exportReviewJson(runId: string): Promise<Record<string, unknown>[]> { return request<Record<string, unknown>[]>(`/api/exports/runs/${runId}/review.json`); }
export function listAuditRuns(): Promise<AuditRun[]> { return request<AuditRun[]>("/api/audit/runs"); }
