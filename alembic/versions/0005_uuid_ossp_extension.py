"""Enable uuid-ossp on Cloud SQL (Phase 9 spec alignment)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_uuid_ossp"
down_revision = "0004_generation_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))


def downgrade() -> None:
    op.execute(sa.text('DROP EXTENSION IF EXISTS "uuid-ossp"'))
