"""replace prd_text with prd_json

Revision ID: f21d9511bf46
Revises: ec842cb13056
Create Date: 2026-06-15 18:46:08.255078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f21d9511bf46'
down_revision: Union[str, Sequence[str], None] = 'ec842cb13056'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("pipeline_runs", sa.Column("prd_json", sa.JSON(), nullable=True))
    op.drop_column("pipeline_runs", "prd_text")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("pipeline_runs", sa.Column("prd_text", sa.Text(), nullable=True))
    op.drop_column("pipeline_runs", "prd_json")
