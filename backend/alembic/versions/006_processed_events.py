"""Add processed_events table for Stripe webhook idempotency

Revision ID: 006_processed_events
Revises: 005_job_indexes
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa

revision = "006_processed_events"
down_revision = "005_job_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", sa.String(255), unique=True, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
