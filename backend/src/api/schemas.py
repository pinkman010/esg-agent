from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from src.domain.enums import ReportStatus, RunStatus
from src.domain.ai_models import AIAssessmentSuggestion
from src.domain.models import AnalysisRun


class ReportUploadResponse(BaseModel):
    report_id: str
    original_filename: str
    file_hash: str
    status: Literal["uploaded"]


class ReportResponse(BaseModel):
    report_id: str
    original_filename: str
    file_hash: str
    page_count: int | None = None
    company_name: str | None = None
    report_year: int | None = None
    language: str | None = None
    status: ReportStatus
    metadata_detected: dict[str, Any]
    metadata_confirmed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    page: int
    page_size: int
    total: int


class ConfirmReportMetadataRequest(BaseModel):
    company_name: str
    report_year: int
    language: str


class AnalyzeResponse(BaseModel):
    run_id: str
    report_id: str
    status: RunStatus
    confirm_llm: bool
    error_message: str | None = None


class DemoResetRequest(BaseModel):
    confirmation: str


class DemoResetResponse(BaseModel):
    cleared_report_count: int
    cleared_runtime_directories: list[Literal["uploads", "derived"]]


class AnalysisStageResponse(BaseModel):
    stage_code: str
    status: str
    completed_units: int
    total_units: int
    error_summary: str | None = None
    created_at: datetime | None = None


class AISummaryResponse(BaseModel):
    eligible: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


class AnalysisRunResponse(AnalysisRun):
    ai_summary: AISummaryResponse


class AssessmentListItem(BaseModel):
    assessment_id: str
    requirement_id: str
    requirement_name_zh: str
    gri_topic: str
    system_verdict: str
    reviewed_verdict: str | None = None
    effective_verdict: str
    risk_level: str
    review_priority: str
    evidence_status: str | None = None
    applicability_status: str | None = None
    risk_reason_codes: list[str]
    review_status: str
    evidence_count: int
    source_pdf_pages: list[int]
    action_status: str | None = None


class AssessmentListResponse(BaseModel):
    items: list[AssessmentListItem]
    page: int
    page_size: int
    total: int


class ReportDashboardResponse(BaseModel):
    report_id: str
    run_id: str | None
    verdict_counts: dict[str, int]
    risk_counts: dict[str, int]
    review_priority_counts: dict[str, int]
    high_risk_total: int
    high_risk_reviewed: int
    high_priority_total: int
    high_priority_reviewed: int
    high_priority_unresolved: int
    applicability_counts: dict[str, int]
    applicability_undetermined_total: int
    failed_requirement_count: int


class BusinessEvidenceItem(BaseModel):
    evidence_id: str
    source_pdf_page: int
    source_report_page: int | None = None
    page_label: str
    evidence_preview: str
    source_method: str
    quality_flags: list[str]
    bbox: dict[str, float] | None = None


class AssessmentDetailResponse(BaseModel):
    assessment_id: str
    requirement_id: str
    requirement_text: str
    source_requirement_text: str
    effective_requirement_text: str
    context_requirement_ids: list[str]
    structure_status: str
    system_verdict: str
    system_rationale: str
    system_rationale_display: str
    system_missing_items: list[str]
    system_missing_items_display: list[str]
    reviewed_verdict: str | None = None
    effective_verdict: str
    review_status: str
    risk_level: str
    review_priority: str
    evidence_status: str | None = None
    applicability_status: str | None = None
    risk_reason_codes: list[str]
    rationale: str
    rationale_display: str
    missing_items: list[str]
    missing_items_display: list[str]
    evidence_items: list[BusinessEvidenceItem]
    latest_snapshot_id: str | None = None
    latest_ai_suggestion: AIAssessmentSuggestion | None = None


class AuditEvent(BaseModel):
    audit_event_id: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime | None = None


class AuditRun(BaseModel):
    run_id: str
    report_id: str
    original_filename: str
    file_hash: str
    status: RunStatus
    model_called: bool
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    events: list[AuditEvent]
