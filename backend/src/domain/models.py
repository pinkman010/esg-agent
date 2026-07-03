from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.domain.enums import (
    AssessmentVerdict,
    EvidenceSourceMethod,
    PageQualityFlag,
    ReviewStatus,
    RunStatus,
)


class Report(BaseModel):
    report_id: str
    original_filename: str
    stored_path: str
    file_hash: str
    page_count: int | None = None
    created_at: datetime | None = None


class AnalysisRun(BaseModel):
    run_id: str
    report_id: str
    status: RunStatus = RunStatus.PENDING
    confirm_llm: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


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
    keywords: list[str] = Field(default_factory=list)
    candidate_pages: list[int] = Field(default_factory=list)
    candidate_page_source: str | None = None
    index_page: int | None = None


class EvidenceItem(BaseModel):
    evidence_id: str
    run_id: str
    report_id: str
    source_text: str
    source_page: int = Field(ge=1)
    source_file_hash: str
    source_method: EvidenceSourceMethod
    bbox: dict[str, float] | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_kpi_evidence: bool = False
    quality_flags: list[PageQualityFlag] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
