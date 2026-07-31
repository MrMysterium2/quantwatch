"""add raw technical/fundamental columns to scores

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scores", sa.Column("current_price", sa.Float(), nullable=True))
    op.add_column("scores", sa.Column("sma50", sa.Float(), nullable=True))
    op.add_column("scores", sa.Column("sma200", sa.Float(), nullable=True))
    op.add_column("scores", sa.Column("rsi", sa.Float(), nullable=True))
    op.add_column("scores", sa.Column("trailing_pe", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("scores", "trailing_pe")
    op.drop_column("scores", "rsi")
    op.drop_column("scores", "sma200")
    op.drop_column("scores", "sma50")
    op.drop_column("scores", "current_price")
