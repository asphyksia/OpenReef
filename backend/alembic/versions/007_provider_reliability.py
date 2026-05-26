"""Add providers table and job reliability fields

Revision ID: 007_provider_reliability
Revises: 006_processed_events
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa

revision = "007_provider_reliability"
down_revision = "006_processed_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create providers table
    op.create_table(
        "providers",
        sa.Column("address", sa.String(255), primary_key=True),
        sa.Column("last_active", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("abandoned_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_abandoned_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Add reliability fields to jobs
    op.add_column("jobs", sa.Column("requeue_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("provider_address", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("last_heartbeat", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "last_heartbeat")
    op.drop_column("jobs", "provider_address")
    op.drop_column("jobs", "requeue_count")
    op.drop_table("providers")
