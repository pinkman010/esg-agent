"""enforce one active analysis run per report

Revision ID: 0009_active_analysis_run_gate
Revises: 0008_export_versions
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_active_analysis_run_gate"
down_revision: str | None = "0008_export_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_analysis_runs_one_active_per_report",
        "analysis_runs",
        ["report_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_analysis_runs_one_active_per_report", table_name="analysis_runs")
