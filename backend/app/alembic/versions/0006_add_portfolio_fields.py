"""add sector, purchase_price, quantity, price_target to watchlist

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("watchlist", sa.Column("sector", sa.String(length=100), nullable=True))
    op.add_column("watchlist", sa.Column("purchase_price", sa.Float(), nullable=True))
    op.add_column("watchlist", sa.Column("quantity", sa.Float(), nullable=True))
    op.add_column("watchlist", sa.Column("price_target", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("watchlist", "price_target")
    op.drop_column("watchlist", "quantity")
    op.drop_column("watchlist", "purchase_price")
    op.drop_column("watchlist", "sector")
