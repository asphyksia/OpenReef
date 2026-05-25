"""Add index on ogpu_task_address and user_id+status composite

Revision ID: 005_job_indexes
Revises: 004_cleanup
Create Date: 2026-05-26

"""
from alembic import op

revision = "005_job_indexes"
down_revision = "004_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_jobs_ogpu_task", "jobs", ["ogpu_task_address"])
    op.create_index("idx_jobs_user_status", "jobs", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_jobs_user_status", "jobs")
    op.drop_index("idx_jobs_ogpu_task", "jobs")
