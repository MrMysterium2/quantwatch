"""add forward_pe, volatility, beta, earnings and news cache to scores

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scores", sa.Column("forward_pe", sa.Float(), nullable=True))
    op.add_column("scores", sa.Column("volatility_pct", sa.Float(), nullable=True))
    op.add_column("scores", sa.Column("beta", sa.Float(), nullable=True))
    op.add_column("scores", sa.Column("next_earnings_date", sa.String(length=20), nullable=True))
    op.add_column("scores", sa.Column("days_to_earnings", sa.Integer(), nullable=True))
    op.add_column("scores", sa.Column("news_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scores", "news_json")
    op.drop_column("scores", "days_to_earnings")
    op.drop_column("scores", "next_earnings_date")
    op.drop_column("scores", "beta")
    op.drop_column("scores", "volatility_pct")
    op.drop_column("scores", "forward_pe")
