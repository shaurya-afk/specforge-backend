"""add google oauth fields to users

Revision ID: 7cda2ae31576
Revises: f21d9511bf46
Create Date: 2026-06-16 22:00:14.526347

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cda2ae31576'
down_revision: Union[str, Sequence[str], None] = 'f21d9511bf46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("google_id", sa.String(), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=False)
