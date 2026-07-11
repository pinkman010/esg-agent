"""add report metadata and lifecycle status

Revision ID: 0003_report_metadata_and_status
Revises: 0002_add_evidence_page_fields
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003_report_metadata_and_status"
down_revision: str | None = "0002_add_evidence_page_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("company_name", sa.String(length=255), nullable=True))
    op.add_column("reports", sa.Column("report_year", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("language", sa.String(length=32), nullable=True))
    op.add_column("reports", sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"))
    op.add_column(
        "reports",
        sa.Column("metadata_detected", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("reports", sa.Column("metadata_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reports", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("reports", sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reports", sa.Column("reopen_reason", sa.Text(), nullable=True))
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_check_constraint("ck_reports_report_year", "reports", "report_year IS NULL OR report_year BETWEEN 1900 AND 2100")
    op.execute(
        """
        UPDATE reports AS r
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM analysis_runs ar
                WHERE ar.report_id = r.report_id AND ar.status = 'completed'
            ) THEN 'analysis_completed'
            WHEN EXISTS (
                SELECT 1 FROM analysis_runs ar
                WHERE ar.report_id = r.report_id AND ar.status = 'failed'
            ) THEN 'analysis_failed'
            ELSE 'uploaded'
        END
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_reports_report_year", "reports", type_="check")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_column("reports", "reopen_reason")
    op.drop_column("reports", "reopened_at")
    op.drop_column("reports", "updated_at")
    op.drop_column("reports", "metadata_confirmed_at")
    op.drop_column("reports", "metadata_detected")
    op.drop_column("reports", "status")
    op.drop_column("reports", "language")
    op.drop_column("reports", "report_year")
    op.drop_column("reports", "company_name")
