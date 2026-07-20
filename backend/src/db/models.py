from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class ReportRecord(Base):
    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    company_name: Mapped[str | None] = mapped_column(String(255))
    report_year: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False, index=True)
    metadata_detected: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    metadata_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopen_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    runs: Mapped[list["AnalysisRunRecord"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class AnalysisRunRecord(Base):
    __tablename__ = "analysis_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confirm_llm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.run_id"), index=True)
    engine_version: Mapped[str] = mapped_column(String(64), default="rules-v1", nullable=False)
    risk_rule_version: Mapped[str] = mapped_column(String(64), default="risk-v1", nullable=False)
    standard_unit_count: Mapped[int | None] = mapped_column(Integer)
    eligible_requirement_count: Mapped[int] = mapped_column(Integer, default=577, nullable=False)
    context_only_count: Mapped[int | None] = mapped_column(Integer)
    method_pending_count: Mapped[int | None] = mapped_column(Integer)
    succeeded_requirement_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_requirement_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    report: Mapped[ReportRecord] = relationship(back_populates="runs")


Index(
    "uq_analysis_runs_one_active_per_report",
    AnalysisRunRecord.report_id,
    unique=True,
    postgresql_where=text("status IN ('pending', 'running')"),
)


class AnalysisStageEventRecord(Base):
    __tablename__ = "analysis_stage_events"

    stage_event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    stage_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("ix_analysis_stage_latest", AnalysisStageEventRecord.run_id, AnalysisStageEventRecord.stage_code, AnalysisStageEventRecord.created_at.desc())


class DocumentPageRecord(Base):
    __tablename__ = "document_pages"

    page_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    source_method: Mapped[str] = mapped_column(String(32), nullable=False)
    page_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class DocumentChunkRecord(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
    source_method: Mapped[str] = mapped_column(String(32), nullable=False)
    source_file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    quality_flags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    embedding_status: Mapped[str | None] = mapped_column(String(32))
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    embedding_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class StandardRequirementRecord(Base):
    __tablename__ = "standard_requirements"

    requirement_pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standard_id: Mapped[str] = mapped_column(String(64), nullable=False)
    standard_version: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)


class DisclosureTaskRecord(Base):
    __tablename__ = "disclosure_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False)
    standard_id: Mapped[str] = mapped_column(String(64), nullable=False)
    standard_version: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_requirement_text: Mapped[str | None] = mapped_column(Text)
    context_requirement_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    structure_status: Mapped[str | None] = mapped_column(String(32))
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)


class AssessmentRecord(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False)
    standard_id: Mapped[str] = mapped_column(String(64), nullable=False)
    standard_version: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    verdict: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    missing_items: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    model_called: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    evidence_items: Mapped[list["EvidenceItemRecord"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")


class AIAssessmentSuggestionRecord(Base):
    __tablename__ = "ai_assessment_suggestions"

    suggestion_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    suggested_verdict: Mapped[str | None] = mapped_column(String(64))
    rationale_zh: Mapped[str | None] = mapped_column(Text)
    missing_items_zh: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    evidence_pdf_pages: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    guardrail_codes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    usage: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    finish_reason: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[object | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_ai_suggestions_confidence"),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_ai_suggestions_latency_ms"),
        CheckConstraint("retry_count >= 0", name="ck_ai_suggestions_retry_count"),
        Index("ix_ai_suggestions_assessment_created", "assessment_id", created_at.desc()),
        Index("ix_ai_suggestions_run_id", "run_id"),
        Index("ix_ai_suggestions_status", "status"),
    )


class AssessmentRiskRecord(Base):
    __tablename__ = "assessment_risks"

    risk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(64))
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    risk_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_status: Mapped[str | None] = mapped_column(String(32), index=True)
    applicability_status: Mapped[str | None] = mapped_column(String(32), index=True)
    trigger_event: Mapped[str] = mapped_column(String(64), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EvidenceItemRecord(Base):
    __tablename__ = "evidence_items"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    report_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
    source_pdf_page: Mapped[int | None] = mapped_column(Integer)
    source_report_page: Mapped[int | None] = mapped_column(Integer)
    source_file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    source_method: Mapped[str] = mapped_column(String(32), nullable=False)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    is_kpi_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    needs_ocr_or_vlm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_ocr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_vlm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ocr_or_vlm_reason: Mapped[str | None] = mapped_column(String(255))
    evidence_preview: Mapped[str | None] = mapped_column(Text)
    evidence_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    assessment: Mapped[AssessmentRecord] = relationship(back_populates="evidence_items")


class RecommendationRecord(Base):
    __tablename__ = "recommendations"

    recommendation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReviewDecisionRecord(Base):
    __tablename__ = "review_decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReviewSnapshotRecord(Base):
    __tablename__ = "review_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("review_snapshots.snapshot_id"))
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_verdict: Mapped[str | None] = mapped_column(String(64))
    reviewed_applicability_status: Mapped[str | None] = mapped_column(String(32))
    evidence_pages: Mapped[list[int] | None] = mapped_column(JSONB)
    evidence_preview: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    missing_items: Mapped[list[str] | None] = mapped_column(JSONB)
    is_batch_operation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("uq_review_snapshot_sequence", "assessment_id", "sequence", unique=True),)


class ReviewChangeEventRecord(Base):
    __tablename__ = "review_change_events"

    change_event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("review_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[object | None] = mapped_column(JSONB)
    new_value: Mapped[object | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ImprovementActionRecord(Base):
    __tablename__ = "improvement_actions"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    owner_name: Mapped[str | None] = mapped_column(String(128))
    due_date: Mapped[date | None] = mapped_column(Date)
    recommendation_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completion_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ExportVersionRecord(Base):
    __tablename__ = "export_versions"

    export_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_version: Mapped[str] = mapped_column(String(64), nullable=False)
    review_scope: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    file_manifest: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    supersedes_export_id: Mapped[str | None] = mapped_column(ForeignKey("export_versions.export_id"))
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)



class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_payload: Mapped[dict] = mapped_column("payload", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("ix_standard_requirement_identity", StandardRequirementRecord.standard_id, StandardRequirementRecord.standard_version, StandardRequirementRecord.requirement_id)
