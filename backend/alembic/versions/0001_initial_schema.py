"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(length=64), primary_key=True),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reports_file_hash", "reports", ["file_hash"])

    op.create_table(
        "analysis_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("report_id", sa.String(length=64), sa.ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confirm_llm", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_analysis_runs_report_id", "analysis_runs", ["report_id"])

    op.create_table(
        "document_pages",
        sa.Column("page_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(length=64), sa.ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_flags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_document_pages_report_id", "document_pages", ["report_id"])

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=64), primary_key=True),
        sa.Column("report_id", sa.String(length=64), sa.ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("source_file_hash", sa.String(length=128), nullable=False),
        sa.Column("bbox", postgresql.JSONB()),
        sa.Column("quality_flags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("embedding_status", sa.String(length=32)),
        sa.Column("embedding_model", sa.String(length=128)),
        sa.Column("embedding_dim", sa.Integer()),
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_document_chunks_report_id", "document_chunks", ["report_id"])

    op.create_table(
        "standard_requirements",
        sa.Column("requirement_pk", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("standard_id", sa.String(length=64), nullable=False),
        sa.Column("standard_version", sa.String(length=64), nullable=False),
        sa.Column("disclosure_id", sa.String(length=128), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("keywords", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_standard_requirement_identity", "standard_requirements", ["standard_id", "standard_version", "requirement_id"])

    op.create_table(
        "disclosure_tasks",
        sa.Column("task_id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", sa.String(length=64), sa.ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_id", sa.String(length=64), nullable=False),
        sa.Column("standard_version", sa.String(length=64), nullable=False),
        sa.Column("disclosure_id", sa.String(length=128), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("keywords", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_disclosure_tasks_run_id", "disclosure_tasks", ["run_id"])

    op.create_table(
        "assessments",
        sa.Column("assessment_id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", sa.String(length=64), sa.ForeignKey("reports.report_id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_id", sa.String(length=64), nullable=False),
        sa.Column("standard_version", sa.String(length=64), nullable=False),
        sa.Column("disclosure_id", sa.String(length=128), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("verdict", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("missing_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_called", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_status", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_assessments_run_id", "assessments", ["run_id"])
    op.create_index("ix_assessments_review_status", "assessments", ["review_status"])

    op.create_table(
        "evidence_items",
        sa.Column("evidence_id", sa.String(length=64), primary_key=True),
        sa.Column("assessment_id", sa.String(length=64), sa.ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.Column("source_file_hash", sa.String(length=128), nullable=False),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("bbox", postgresql.JSONB()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_kpi_evidence", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quality_flags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_evidence_items_assessment_id", "evidence_items", ["assessment_id"])

    op.create_table(
        "recommendations",
        sa.Column("recommendation_id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("disclosure_id", sa.String(length=128), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendations_run_id", "recommendations", ["run_id"])

    op.create_table(
        "review_decisions",
        sa.Column("decision_id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", sa.String(length=64), sa.ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_status", sa.String(length=64), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_review_decisions_run_id", "review_decisions", ["run_id"])
    op.create_index("ix_review_decisions_assessment_id", "review_decisions", ["assessment_id"])

    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=64)),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_run_id", "audit_events", ["run_id"])


def downgrade() -> None:
    for table_name in [
        "audit_events",
        "review_decisions",
        "recommendations",
        "evidence_items",
        "assessments",
        "disclosure_tasks",
        "standard_requirements",
        "document_chunks",
        "document_pages",
        "analysis_runs",
        "reports",
    ]:
        op.drop_table(table_name)