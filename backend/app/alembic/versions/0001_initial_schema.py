"""initial schema: watchlist + scores

Revision ID: 0001
Revises:
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watchlist_ticker", "watchlist", ["ticker"], unique=True)

    empfehlung_enum = sa.Enum("kaufen", "halten", "verkaufen", name="empfehlung")

    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recommendation", empfehlung_enum, nullable=False),
        sa.Column("expected_return_pct", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("technical_score", sa.Float(), nullable=True),
        sa.Column("fundamental_score", sa.Float(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
    )
    op.create_index("ix_scores_ticker", "scores", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_scores_ticker", table_name="scores")
    op.drop_table("scores")
    op.drop_index("ix_watchlist_ticker", table_name="watchlist")
    op.drop_table("watchlist")
    sa.Enum(name="empfehlung").drop(op.get_bind(), checkfirst=True)
