"""Add ogpu_task_address column to jobs

Revision ID: 003_ogpu_task_address
Revises: 002_seed_models
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa

revision = "003_ogpu_task_address"
down_revision = "002_seed_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("ogpu_task_address", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "ogpu_task_address")
