import type {
  AnalysisRun,
  AnalyzeResponse,
  AuditRun,
  DisclosureAssessment,
  Recommendation,
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
export function analyzeReport(reportId: string, confirmLlm: boolean): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(`/api/reports/${reportId}/analyze`, { method: "POST", body: { confirm_llm: confirmLlm } });
}
export function listRuns(): Promise<AnalysisRun[]> { return request<AnalysisRun[]>("/api/runs"); }
export function getRun(runId: string): Promise<AnalysisRun> { return request<AnalysisRun>(`/api/runs/${runId}`); }
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