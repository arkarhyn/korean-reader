"""grammar_point.teach_order + grammar_point.lesson (Stage 8 grammar track)

`teach_order` overrides htsk_lesson for the order lessons are taught in (priority
threads such as -는데 come before HTSK teaches them). `lesson` is the lesson card
(Japanese parallel, notes, 2 examples, select-only drills) from
content/grammar/lessons/<code>.json; NULL until one is written.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('grammar_point') as batch:
        batch.add_column(sa.Column('teach_order', sa.Float(), nullable=True))
        batch.add_column(sa.Column('lesson', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('grammar_point') as batch:
        batch.drop_column('lesson')
        batch.drop_column('teach_order')
