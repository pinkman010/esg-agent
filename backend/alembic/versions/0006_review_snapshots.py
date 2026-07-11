"""add append-only review snapshots

Revision ID: 0006_review_snapshots
Revises: 0005_assessment_risks
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_review_snapshots"
down_revision: str | None = "0005_assessment_risks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_snapshots",
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("assessment_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("previous_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("reviewer_name", sa.String(length=128), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewed_verdict", sa.String(length=64), nullable=True),
        sa.Column("evidence_pages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_preview", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("missing_items", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_batch_operation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("batch_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.assessment_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_snapshot_id"], ["review_snapshots.snapshot_id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index("ix_review_snapshots_assessment_id", "review_snapshots", ["assessment_id"])
    op.create_index("ix_review_snapshots_run_id", "review_snapshots", ["run_id"])
    op.create_index("uq_review_snapshot_sequence", "review_snapshots", ["assessment_id", "sequence"], unique=True)
    op.create_table(
        "review_change_events",
        sa.Column("change_event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["review_snapshots.snapshot_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("change_event_id"),
    )
    op.create_index("ix_review_change_events_snapshot_id", "review_change_events", ["snapshot_id"])
    op.execute(
        """
        INSERT INTO review_snapshots (
            snapshot_id, assessment_id, run_id, sequence, operation_type,
            reviewer_name, reason_code, reviewer_note, created_at
        )
        SELECT
            left('legacy-' || decision_id, 64),
            assessment_id,
            run_id,
            row_number() OVER (PARTITION BY assessment_id ORDER BY decided_at, decision_id),
            'legacy_import',
            '历史复核',
            'legacy_review_decision',
            reviewer_note,
            decided_at
        FROM review_decisions
        """
    )


def downgrade() -> None:
    op.drop_index("ix_review_change_events_snapshot_id", table_name="review_change_events")
    op.drop_table("review_change_events")
    op.drop_index("uq_review_snapshot_sequence", table_name="review_snapshots")
    op.drop_index("ix_review_snapshots_run_id", table_name="review_snapshots")
    op.drop_index("ix_review_snapshots_assessment_id", table_name="review_snapshots")
    op.drop_table("review_snapshots")
