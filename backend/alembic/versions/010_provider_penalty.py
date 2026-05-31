"""Add provider blocking fields

Revision ID: 010_provider_penalty
Revises: 009_dataset_tokens
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "010_provider_penalty"
down_revision = "009_dataset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("providers", sa.Column("blocked_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("providers", sa.Column("blocked_reason", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("providers", "blocked_reason")
    op.drop_column("providers", "blocked_at")
    op.drop_column("providers", "is_blocked")
