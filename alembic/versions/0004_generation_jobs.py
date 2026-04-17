"""Add generation_jobs table for Phase 7 brief generation."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004_generation_jobs"
down_revision = "0003_brand_events_vector_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("pipeline_stage", sa.String(64), nullable=True),
        sa.Column("request_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column("summary_json", JSONB, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_generation_jobs_brand_id", "generation_jobs", ["brand_id"])
    op.create_index(
        "ix_generation_jobs_brand_created",
        "generation_jobs",
        ["brand_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_brand_created", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_brand_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
