"""Add token_count column to datasets table

Revision ID: 009_dataset_tokens
Revises: 008_provider_hardware
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "009_dataset_tokens"
down_revision = "008_provider_hardware"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("token_count", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("datasets", "token_count")
