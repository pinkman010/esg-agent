from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.domain.enums import (
    ApplicabilityStatus,
    AssessmentVerdict,
    ActionPriority,
    ActionStatus,
    EvidenceSourceMethod,
    EvidenceStatus,
    PageQualityFlag,
    ReportStatus,
    RiskLevel,
    ReviewStatus,
    ReviewOperation,
    RunStatus,
)


class Report(BaseModel):
    report_id: str
    original_filename: str
    stored_path: str
    file_hash: str
    page_count: int | None = None
    company_name: str | None = None
    report_year: int | None = Field(default=None, ge=1900, le=2100)
    language: str | None = None
    status: ReportStatus = ReportStatus.UPLOADED
    metadata_detected: dict[str, Any] = Field(default_factory=dict)
    metadata_confirmed_at: datetime | None = None
    updated_at: datetime | None = None
    reopened_at: datetime | None = None
    reopen_reason: str | None = None
    created_at: datetime | None = None


class AnalysisRun(BaseModel):
    run_id: str
    report_id: str
    status: RunStatus = RunStatus.PENDING
    confirm_llm: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    parent_run_id: str | None = None
    engine_version: str = "rules-v1"
    risk_rule_version: str = "risk-v1"
    standard_unit_count: int = Field(default=577, ge=0)
    eligible_requirement_count: int = Field(default=577, ge=0)
    context_only_count: int = Field(default=0, ge=0)
    method_pending_count: int = Field(default=0, ge=0)
    succeeded_requirement_count: int = Field(default=0, ge=0)
    failed_requirement_count: int = Field(default=0, ge=0)
    failure_summary: dict[str, Any] = Field(default_factory=dict)


class AnalysisStageEvent(BaseModel):
    stage_event_id: int | None = None
    run_id: str
    stage_code: str
    status: str
    completed_units: int = Field(default=0, ge=0)
    total_units: int = Field(default=0, ge=0)
    error_summary: str | None = None
    created_at: datetime | None = None


class AssessmentRisk(BaseModel):
    risk_id: str
    assessment_id: str
    snapshot_id: str | None = None
    risk_level: RiskLevel
    reason_codes: list[str] = Field(default_factory=list)
    risk_rule_version: str = "risk-v1"
    evidence_status: EvidenceStatus | None = None
    applicability_status: ApplicabilityStatus | None = None
    trigger_event: str
    calculated_at: datetime | None = None


class PageExtraction(BaseModel):
    report_id: str
    page_number: int = Field(ge=1)
    text: str = ""
    image_count: int = Field(default=0, ge=0)
    table_count: int = Field(default=0, ge=0)
    quality_flags: list[PageQualityFlag] = Field(default_factory=list)
    source_method: EvidenceSourceMethod = EvidenceSourceMethod.PDFPLUMBER
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    report_id: str
    text: str
    source_page: int = Field(ge=1)
    source_method: EvidenceSourceMethod
    source_file_hash: str
    bbox: dict[str, float] | None = None
    quality_flags: list[PageQualityFlag] = Field(default_factory=list)
    embedding_status: str | None = None
    embedding_model: str | None = None
    embedding_dim: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DisclosureRequirement(BaseModel):
    standard_id: str
    standard_version: str
    disclosure_id: str
    requirement_id: str
    requirement_text: str
    keywords: list[str] = Field(default_factory=list)


class DisclosureTask(BaseModel):
    task_id: str
    run_id: str
    report_id: str
    standard_id: str
    standard_version: str
    disclosure_id: str
    requirement_id: str
    requirement_text: str
    source_requirement_text: str | None = None
    context_requirement_ids: list[str] = Field(default_factory=list)
    structure_status: str = "verified"
    keywords: list[str] = Field(default_factory=list)
    candidate_pages: list[int] = Field(default_factory=list)
    candidate_pdf_pages: list[int] = Field(default_factory=list)
    candidate_report_pages: list[int | None] = Field(default_factory=list)
    candidate_page_source: str | None = None
    index_page: int | None = None
    report_index_pdf_page: int | None = None
    report_index_report_page: int | None = None
    excluded_pdf_pages: list[int] = Field(default_factory=list)
    kpi_table_pages: list[int] = Field(default_factory=list)
    kpi_metric_terms: list[str] = Field(default_factory=list)
    kpi_year_columns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def default_candidate_pdf_pages(self) -> "DisclosureTask":
        if self.source_requirement_text is None:
            self.source_requirement_text = self.requirement_text
        if not self.candidate_pdf_pages and self.candidate_pages:
            self.candidate_pdf_pages = list(self.candidate_pages)
        return self


class EvidenceItem(BaseModel):
    evidence_id: str
    run_id: str
    report_id: str
    source_text: str
    source_page: int = Field(ge=1)
    source_pdf_page: int | None = Field(default=None, ge=1)
    source_report_page: int | None = Field(default=None, ge=1)
    source_file_hash: str
    source_method: EvidenceSourceMethod
    bbox: dict[str, float] | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_kpi_evidence: bool = False
    quality_flags: list[PageQualityFlag] = Field(default_factory=list)
    needs_ocr_or_vlm: bool = False
    requires_ocr: bool = False
    requires_vlm: bool = False
    ocr_or_vlm_reason: str | None = None
    evidence_preview: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def default_source_pdf_page(self) -> "EvidenceItem":
        if self.source_pdf_page is None:
            self.source_pdf_page = self.source_page
        if self.evidence_preview is None:
            preview = " ".join(self.source_text.split())
            self.evidence_preview = preview[:200] + "..." if len(preview) > 200 else preview
        return self


class DisclosureAssessment(BaseModel):
    assessment_id: str
    run_id: str
    report_id: str
    standard_id: str
    standard_version: str
    disclosure_id: str
    requirement_id: str
    verdict: AssessmentVerdict
    rationale: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    model_called: bool = False
    review_status: ReviewStatus = ReviewStatus.NOT_REQUIRED

    @model_validator(mode="after")
    def enforce_evidence_and_review_rules(self) -> "DisclosureAssessment":
        if not self.evidence and self.verdict is not AssessmentVerdict.UNKNOWN:
            raise ValueError("evidence is required for a non-unknown disclosure verdict")

        if not self.evidence:
            self.review_status = ReviewStatus.NEEDS_MANUAL_REVIEW
            return self

        has_low_confidence_kpi = any(
            item.is_kpi_evidence
            and item.source_method in {EvidenceSourceMethod.OCR, EvidenceSourceMethod.VLM}
            for item in self.evidence
        )
        if has_low_confidence_kpi:
            self.review_status = ReviewStatus.NEEDS_MANUAL_REVIEW

        return self


class Recommendation(BaseModel):
    recommendation_id: str
    run_id: str
    report_id: str
    disclosure_id: str
    requirement_id: str
    recommendation_text: str
    created_at: datetime | None = None


class ReviewDecision(BaseModel):
    decision_id: str
    run_id: str
    assessment_id: str
    review_status: ReviewStatus
    reviewer_note: str = ""
    decided_at: datetime | None = None


class ReviewSnapshot(BaseModel):
    snapshot_id: str
    assessment_id: str
    run_id: str
    sequence: int = Field(ge=1)
    previous_snapshot_id: str | None = None
    operation_type: ReviewOperation
    reviewer_name: str
    reason_code: str
    reviewer_note: str = ""
    reviewed_verdict: AssessmentVerdict | None = None
    reviewed_applicability_status: ApplicabilityStatus | None = None
    evidence_pages: list[int] | None = None
    evidence_preview: str | None = None
    rationale: str | None = None
    missing_items: list[str] | None = None
    is_batch_operation: bool = False
    batch_id: str | None = None
    created_at: datetime | None = None


class ReviewChangeEvent(BaseModel):
    change_event_id: int | None = None
    snapshot_id: str
    field_name: str
    old_value: Any = None
    new_value: Any = None
    created_at: datetime | None = None


class ImprovementAction(BaseModel):
    action_id: str
    report_id: str
    assessment_id: str
    title: str
    priority: ActionPriority = ActionPriority.MEDIUM
    status: ActionStatus = ActionStatus.OPEN
    owner_name: str | None = None
    due_date: date | None = None
    recommendation_text: str = ""
    completion_note: str | None = None
    created_by: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExportVersion(BaseModel):
    export_id: str
    report_id: str
    run_id: str
    version_number: int = Field(ge=0)
    status: str
    is_draft: bool
    file_hash: str
    engine_version: str
    risk_rule_version: str
    requirement_version: str = "gri-eligible-577-v1"
    review_scope: dict[str, Any] = Field(default_factory=dict)
    file_manifest: list[dict[str, Any]] = Field(default_factory=list)
    supersedes_export_id: str | None = None
    created_by: str
    created_at: datetime | None = None
