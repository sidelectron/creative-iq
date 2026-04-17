"""Create all Phase 1 tables and enable pgvector."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from shared.models.db import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    op.execute(sa.text("DROP EXTENSION IF EXISTS vector CASCADE"))
