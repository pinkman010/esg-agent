"""add standard structure fields and append-only AI suggestions

Revision ID: 0011_ai_suggestions
Revises: 0010_risk_v2_dimensions
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_ai_suggestions"
down_revision: str | None = "0010_risk_v2_dimensions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("standard_unit_count", sa.Integer(), nullable=True))
    op.add_column("analysis_runs", sa.Column("context_only_count", sa.Integer(), nullable=True))
    op.add_column("analysis_runs", sa.Column("method_pending_count", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_analysis_runs_standard_unit_count",
        "analysis_runs",
        "standard_unit_count IS NULL OR standard_unit_count >= 0",
    )
    op.create_check_constraint(
        "ck_analysis_runs_context_only_count",
        "analysis_runs",
        "context_only_count IS NULL OR context_only_count >= 0",
    )
    op.create_check_constraint(
        "ck_analysis_runs_method_pending_count",
        "analysis_runs",
        "method_pending_count IS NULL OR method_pending_count >= 0",
    )

    op.add_column("disclosure_tasks", sa.Column("source_requirement_text", sa.Text(), nullable=True))
    op.add_column(
        "disclosure_tasks",
        sa.Column("context_requirement_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("disclosure_tasks", sa.Column("structure_status", sa.String(length=32), nullable=True))

    op.create_table(
        "ai_assessment_suggestions",
        sa.Column("suggestion_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "assessment_id",
            sa.String(length=64),
            sa.ForeignKey("assessments.assessment_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(length=64),
            sa.ForeignKey("analysis_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("suggested_verdict", sa.String(length=64), nullable=True),
        sa.Column("rationale_zh", sa.Text(), nullable=True),
        sa.Column("missing_items_zh", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_pdf_pages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("guardrail_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("finish_reason", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_ai_suggestions_confidence",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_ai_suggestions_latency_ms",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_ai_suggestions_retry_count"),
    )
    op.create_index(
        "ix_ai_suggestions_assessment_created",
        "ai_assessment_suggestions",
        ["assessment_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_ai_suggestions_run_id",
        "ai_assessment_suggestions",
        ["run_id"],
    )
    op.create_index(
        "ix_ai_suggestions_status",
        "ai_assessment_suggestions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_suggestions_status", table_name="ai_assessment_suggestions")
    op.drop_index("ix_ai_suggestions_run_id", table_name="ai_assessment_suggestions")
    op.drop_index(
        "ix_ai_suggestions_assessment_created",
        table_name="ai_assessment_suggestions",
    )
    op.drop_table("ai_assessment_suggestions")

    op.drop_column("disclosure_tasks", "structure_status")
    op.drop_column("disclosure_tasks", "context_requirement_ids")
    op.drop_column("disclosure_tasks", "source_requirement_text")

    op.drop_constraint(
        "ck_analysis_runs_method_pending_count", "analysis_runs", type_="check"
    )
    op.drop_constraint(
        "ck_analysis_runs_context_only_count", "analysis_runs", type_="check"
    )
    op.drop_constraint(
        "ck_analysis_runs_standard_unit_count", "analysis_runs", type_="check"
    )
    op.drop_column("analysis_runs", "method_pending_count")
    op.drop_column("analysis_runs", "context_only_count")
    op.drop_column("analysis_runs", "standard_unit_count")
