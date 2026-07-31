import os
import sys
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Base  # noqa: E402
from models import Score, Watchlist  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# WICHTIG: DB-URL bewusst NICHT über config.set_main_option() setzen.
# Alembic nutzt intern configparser, und dessen Standard-Interpolation behandelt "%"
# als Platzhalter-Zeichen. URL-encodete Sonderzeichen im Passwort (z. B. "%40" für "@")
# loesen dann "invalid interpolation syntax" aus. Deshalb wird die URL hier als eigene
# Variable gehalten und direkt an create_engine() uebergeben, am ConfigParser vorbei.
pg_user = quote_plus(os.getenv("POSTGRES_USER", ""))
pg_password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
pg_db = os.getenv("POSTGRES_DB", "")
db_url = f"postgresql://{pg_user}:{pg_password}@aktien-db:5432/{pg_db}"


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(db_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
