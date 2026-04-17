"""Add pgvector index for brand_events embeddings."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_brand_events_vector_index"
down_revision = "0002_add_sync_state_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_brand_events_embedding_hnsw
            ON brand_events
            USING hnsw (embedding vector_cosine_ops)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_brand_events_embedding_hnsw"))
