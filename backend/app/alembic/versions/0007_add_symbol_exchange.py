"""add symbol and exchange to watchlist

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("watchlist", sa.Column("symbol", sa.String(length=20), nullable=True))
    op.add_column("watchlist", sa.Column("exchange", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("watchlist", "exchange")
    op.drop_column("watchlist", "symbol")
