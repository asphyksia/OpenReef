"""Add job metrics columns for analytics export.

Adds training_duration_seconds and gpu_type to the jobs table.
These fields are populated when a job completes and are used for
pricing optimization and efficiency analysis.
"""

from alembic import op
import sqlalchemy as sa

revision = "013_job_metrics"
down_revision = "6f13b3d5fb42"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("training_duration_seconds", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("gpu_type", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("jobs", "gpu_type")
    op.drop_column("jobs", "training_duration_seconds")
