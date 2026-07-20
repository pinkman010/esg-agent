"""add risk-v2.1 review dimensions

Revision ID: 0010_risk_v2_dimensions
Revises: 0009_active_analysis_run_gate
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_risk_v2_dimensions"
down_revision: str | None = "0009_active_analysis_run_gate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assessment_risks",
        sa.Column("evidence_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "assessment_risks",
        sa.Column("applicability_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "review_snapshots",
        sa.Column("reviewed_applicability_status", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_assessment_risks_evidence_status",
        "assessment_risks",
        ["evidence_status"],
    )
    op.create_index(
        "ix_assessment_risks_applicability_status",
        "assessment_risks",
        ["applicability_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assessment_risks_applicability_status",
        table_name="assessment_risks",
    )
    op.drop_index(
        "ix_assessment_risks_evidence_status",
        table_name="assessment_risks",
    )
    op.drop_column("review_snapshots", "reviewed_applicability_status")
    op.drop_column("assessment_risks", "applicability_status")
    op.drop_column("assessment_risks", "evidence_status")
