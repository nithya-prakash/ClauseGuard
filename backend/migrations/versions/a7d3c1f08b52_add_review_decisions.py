"""add review_decisions table

Revision ID: a7d3c1f08b52
Revises: c0e5717141c2
Create Date: 2026-10-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3c1f08b52'
down_revision: Union[str, Sequence[str], None] = 'c0e5717141c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('review_decisions',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('decisions_json', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('document_id')
    )


def downgrade() -> None:
    op.drop_table('review_decisions')
