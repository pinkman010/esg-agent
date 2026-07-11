"""add versioned exports

Revision ID: 0008_export_versions
Revises: 0007_improvement_actions
Create Date: 2026-07-11
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_export_versions"
down_revision: str | None = "0007_improvement_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_versions",
        sa.Column("export_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_draft", sa.Boolean(), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("risk_rule_version", sa.String(length=64), nullable=False),
        sa.Column("requirement_version", sa.String(length=64), nullable=False),
        sa.Column("review_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("file_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supersedes_export_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.report_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_export_id"], ["export_versions.export_id"]),
        sa.PrimaryKeyConstraint("export_id"),
    )
    op.create_index("ix_export_versions_report_id", "export_versions", ["report_id"])
    op.create_index("ix_export_versions_run_id", "export_versions", ["run_id"])
    op.create_index(
        "uq_formal_export_version",
        "export_versions",
        ["report_id", "version_number"],
        unique=True,
        postgresql_where=sa.text("is_draft = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_formal_export_version", table_name="export_versions")
    op.drop_index("ix_export_versions_run_id", table_name="export_versions")
    op.drop_index("ix_export_versions_report_id", table_name="export_versions")
    op.drop_table("export_versions")
