"""add users table and user_id to watchlist

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.execute("DELETE FROM watchlist")

    op.drop_index("ix_watchlist_ticker", table_name="watchlist")
    op.add_column("watchlist", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        "fk_watchlist_user", "watchlist", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"])
    op.create_index("ix_watchlist_ticker", "watchlist", ["ticker"])
    op.create_unique_constraint("uq_watchlist_user_ticker", "watchlist", ["user_id", "ticker"])


def downgrade() -> None:
    op.drop_constraint("uq_watchlist_user_ticker", "watchlist", type_="unique")
    op.drop_index("ix_watchlist_ticker", table_name="watchlist")
    op.drop_index("ix_watchlist_user_id", table_name="watchlist")
    op.drop_constraint("fk_watchlist_user", "watchlist", type_="foreignkey")
    op.drop_column("watchlist", "user_id")
    op.create_index("ix_watchlist_ticker", "watchlist", ["ticker"], unique=True)

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
