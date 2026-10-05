"""lexeme_state / grammar_state base_state + base_source (Stage 6 replay baseline)

The baseline is what placement and the seed wrote; `state`, `fsrs_card`,
`exposures` and `lookups` are re-derived from it by replaying the event log
(app/srs.py). Existing placement rows keep their state as the baseline; the
rest is backfilled by `scripts/derive_srs.py --rebase`.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('lexeme_state', 'grammar_state')


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('base_state', sa.String(), nullable=True))
            batch.add_column(sa.Column('base_source', sa.String(), nullable=True))
        op.execute(f"UPDATE {table} SET base_state = state, base_source = source WHERE source = 'placement'")
    # Offsets of the word inside sentence_ko, for highlighting in Quick review.
    with op.batch_alter_table('context_sentence') as batch:
        batch.add_column(sa.Column('start', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('end', sa.Integer(), nullable=True))
        batch.create_index('ix_context_sentence_origin', ['origin'])


def downgrade() -> None:
    with op.batch_alter_table('context_sentence') as batch:
        batch.drop_index('ix_context_sentence_origin')
        batch.drop_column('end')
        batch.drop_column('start')
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column('base_source')
            batch.drop_column('base_state')
