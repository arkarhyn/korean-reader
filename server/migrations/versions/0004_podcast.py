"""episode.media + episode_paragraph.meta (Stage 7 podcast parts)

`media` holds a podcast part's YouTube id and time range; `meta` holds a turn's
speaker and its timed subtitle lines. Both are NULL for authored episodes.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('episode') as batch:
        batch.add_column(sa.Column('media', sa.JSON(), nullable=True))
    with op.batch_alter_table('episode_paragraph') as batch:
        batch.add_column(sa.Column('meta', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('episode_paragraph') as batch:
        batch.drop_column('meta')
    with op.batch_alter_table('episode') as batch:
        batch.drop_column('media')
