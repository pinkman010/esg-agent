"""add improvement actions

Revision ID: 0007_improvement_actions
Revises: 0006_review_snapshots
Create Date: 2026-07-11
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0007_improvement_actions"
down_revision: str | None = "0006_review_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "improvement_actions",
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner_name", sa.String(length=128), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("recommendation_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("completion_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.report_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.assessment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index("ix_improvement_actions_report_id", "improvement_actions", ["report_id"])
    op.create_index("ix_improvement_actions_assessment_id", "improvement_actions", ["assessment_id"])
    op.create_index("ix_improvement_actions_status", "improvement_actions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_improvement_actions_status", table_name="improvement_actions")
    op.drop_index("ix_improvement_actions_assessment_id", table_name="improvement_actions")
    op.drop_index("ix_improvement_actions_report_id", table_name="improvement_actions")
    op.drop_table("improvement_actions")
