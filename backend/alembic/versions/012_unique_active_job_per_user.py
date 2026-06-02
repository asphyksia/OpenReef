"""unique_active_job_per_user

Revision ID: 012_unique_active_job
Revises: 6f13b3d5fb42
Create Date: 2026-06-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '012_unique_active_job'
down_revision: Union[str, None] = '6f13b3d5fb42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index: only one active job per user at a time
    # Active statuses: pending, queued, provisioning, running, checkpointing
    op.execute("""
        CREATE UNIQUE INDEX ux_one_active_job_per_user ON jobs (user_id)
        WHERE status IN ('pending', 'queued', 'provisioning', 'running', 'checkpointing')
    """)


def downgrade() -> None:
    op.drop_index("ux_one_active_job_per_user", table_name="jobs")
