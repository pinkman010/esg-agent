from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
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

    report: Mapped[ReportRecord] = relationship(back_populates="runs")


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


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_payload: Mapped[dict] = mapped_column("payload", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("ix_standard_requirement_identity", StandardRequirementRecord.standard_id, StandardRequirementRecord.standard_version, StandardRequirementRecord.requirement_id)
