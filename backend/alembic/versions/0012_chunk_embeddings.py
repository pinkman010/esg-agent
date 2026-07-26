"""add document chunk embeddings

Revision ID: 0012_chunk_embeddings
Revises: 0011_ai_suggestions
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0012_chunk_embeddings"
down_revision: str | None = "0011_ai_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_chunk_embeddings",
        sa.Column(
            "chunk_id",
            sa.String(length=64),
            sa.ForeignKey("document_chunks.chunk_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider", sa.String(length=64), primary_key=True),
        sa.Column("model", sa.String(length=128), primary_key=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "embedding_dim = 1024",
            name="ck_chunk_embeddings_dim_1024",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="ck_chunk_embeddings_status",
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND embedding IS NOT NULL) OR "
            "(status = 'failed' AND embedding IS NULL)",
            name="ck_chunk_embeddings_status_vector",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_chunk_embeddings_latency_ms",
        ),
        sa.CheckConstraint(
            "retry_count >= 0",
            name="ck_chunk_embeddings_retry_count",
        ),
    )
    op.create_index(
        "ix_chunk_embeddings_provider_model",
        "document_chunk_embeddings",
        ["provider", "model"],
    )
    op.create_index(
        "ix_chunk_embeddings_status",
        "document_chunk_embeddings",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chunk_embeddings_status",
        table_name="document_chunk_embeddings",
    )
    op.drop_index(
        "ix_chunk_embeddings_provider_model",
        table_name="document_chunk_embeddings",
    )
    op.drop_table("document_chunk_embeddings")
