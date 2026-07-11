"""add analysis stages and partial run statistics

Revision ID: 0004_analysis_stages
Revises: 0003_report_metadata_and_status
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_analysis_stages"
down_revision: str | None = "0003_report_metadata_and_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("parent_run_id", sa.String(length=64), nullable=True))
    op.add_column("analysis_runs", sa.Column("engine_version", sa.String(length=64), nullable=False, server_default="rules-v1"))
    op.add_column("analysis_runs", sa.Column("risk_rule_version", sa.String(length=64), nullable=False, server_default="risk-v1"))
    op.add_column("analysis_runs", sa.Column("eligible_requirement_count", sa.Integer(), nullable=False, server_default="577"))
    op.add_column("analysis_runs", sa.Column("succeeded_requirement_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("analysis_runs", sa.Column("failed_requirement_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "analysis_runs",
        sa.Column("failure_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_foreign_key("fk_analysis_runs_parent", "analysis_runs", "analysis_runs", ["parent_run_id"], ["run_id"])
    op.create_index("ix_analysis_runs_parent_run_id", "analysis_runs", ["parent_run_id"])
    op.create_table(
        "analysis_stage_events",
        sa.Column("stage_event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("stage_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("completed_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("stage_event_id"),
    )
    op.create_index("ix_analysis_stage_events_run_id", "analysis_stage_events", ["run_id"])
    op.create_index("ix_analysis_stage_latest", "analysis_stage_events", ["run_id", "stage_code", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_analysis_stage_latest", table_name="analysis_stage_events")
    op.drop_index("ix_analysis_stage_events_run_id", table_name="analysis_stage_events")
    op.drop_table("analysis_stage_events")
    op.drop_index("ix_analysis_runs_parent_run_id", table_name="analysis_runs")
    op.drop_constraint("fk_analysis_runs_parent", "analysis_runs", type_="foreignkey")
    op.drop_column("analysis_runs", "failure_summary")
    op.drop_column("analysis_runs", "failed_requirement_count")
    op.drop_column("analysis_runs", "succeeded_requirement_count")
    op.drop_column("analysis_runs", "eligible_requirement_count")
    op.drop_column("analysis_runs", "risk_rule_version")
    op.drop_column("analysis_runs", "engine_version")
    op.drop_column("analysis_runs", "parent_run_id")
