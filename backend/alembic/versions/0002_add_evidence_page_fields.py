"""add evidence page fields

Revision ID: 0002_add_evidence_page_fields
Revises: 0001_initial_schema
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_add_evidence_page_fields"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("evidence_items", sa.Column("source_pdf_page", sa.Integer(), nullable=True))
    op.add_column("evidence_items", sa.Column("source_report_page", sa.Integer(), nullable=True))
    op.add_column(
        "evidence_items",
        sa.Column("needs_ocr_or_vlm", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "evidence_items",
        sa.Column("requires_ocr", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "evidence_items",
        sa.Column("requires_vlm", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("evidence_items", sa.Column("ocr_or_vlm_reason", sa.String(length=255), nullable=True))
    op.add_column("evidence_items", sa.Column("evidence_preview", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence_items", "evidence_preview")
    op.drop_column("evidence_items", "ocr_or_vlm_reason")
    op.drop_column("evidence_items", "requires_vlm")
    op.drop_column("evidence_items", "requires_ocr")
    op.drop_column("evidence_items", "needs_ocr_or_vlm")
    op.drop_column("evidence_items", "source_report_page")
    op.drop_column("evidence_items", "source_pdf_page")
