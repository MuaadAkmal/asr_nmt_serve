"""Add callback_url to jobs table

Revision ID: 002_add_callback_url
Revises: 001_initial
Create Date: 2026-02-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_callback_url'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add callback_url column to jobs table
    op.add_column(
        'jobs',
        sa.Column('callback_url', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('jobs', 'callback_url')
