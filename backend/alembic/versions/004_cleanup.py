"""Remove stale ogpu_node_id column from jobs

Revision ID: 004_cleanup
Revises: 003_ogpu_task_address
Create Date: 2026-05-25

"""
from alembic import op

revision = "004_cleanup"
down_revision = "003_ogpu_task_address"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("jobs", "ogpu_node_id")


def downgrade() -> None:
    op.add_column("jobs", op.column("ogpu_node_id", op.String(100), nullable=True))
