"""episode.summary (one-line continuity note for the generator)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('episode') as batch:
        batch.add_column(sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('episode') as batch:
        batch.drop_column('summary')
