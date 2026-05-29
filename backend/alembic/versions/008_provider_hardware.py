"""Add hardware fields to providers table for SmartRoute

Revision ID: 008_provider_hardware
Revises: 007_provider_reliability
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = "008_provider_hardware"
down_revision = "007_provider_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("environment", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("gpu_model", sa.String(255), nullable=True))
    op.add_column("providers", sa.Column("vram_gb", sa.Float(), nullable=True))
    op.add_column("providers", sa.Column("cpu_model", sa.String(255), nullable=True))
    op.add_column("providers", sa.Column("ram_gb", sa.Float(), nullable=True))
    op.add_column("providers", sa.Column("base_data_url", sa.String(512), nullable=True))
    op.add_column("providers", sa.Column("last_sync", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("providers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("providers", "is_active")
    op.drop_column("providers", "last_sync")
    op.drop_column("providers", "base_data_url")
    op.drop_column("providers", "ram_gb")
    op.drop_column("providers", "cpu_model")
    op.drop_column("providers", "vram_gb")
    op.drop_column("providers", "gpu_model")
    op.drop_column("providers", "environment")
