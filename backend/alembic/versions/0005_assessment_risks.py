"""add append-only assessment risks

Revision ID: 0005_assessment_risks
Revises: 0004_analysis_stages
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_assessment_risks"
down_revision: str | None = "0004_analysis_stages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_risks",
        sa.Column("risk_id", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("risk_rule_version", sa.String(length=64), nullable=False),
        sa.Column("trigger_event", sa.String(length=64), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.assessment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("risk_id"),
    )
    op.create_index("ix_assessment_risks_assessment_id", "assessment_risks", ["assessment_id"])
    op.create_index("ix_assessment_risks_risk_level", "assessment_risks", ["risk_level"])


def downgrade() -> None:
    op.drop_index("ix_assessment_risks_risk_level", table_name="assessment_risks")
    op.drop_index("ix_assessment_risks_assessment_id", table_name="assessment_risks")
    op.drop_table("assessment_risks")
