"""add_index_users_is_verified

Revision ID: 6f13b3d5fb42
Revises: 010_provider_penalty
Create Date: 2026-06-01 23:43:00.853916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f13b3d5fb42'
down_revision: Union[str, None] = '010_provider_penalty'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_users_is_verified", "users", ["is_verified"])


def downgrade() -> None:
    op.drop_index("ix_users_is_verified", table_name="users")
