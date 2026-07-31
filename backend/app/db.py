import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

pg_user = quote_plus(os.getenv("POSTGRES_USER", ""))
pg_password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
pg_db = os.getenv("POSTGRES_DB", "")

DATABASE_URL = f"postgresql://{pg_user}:{pg_password}@aktien-db:5432/{pg_db}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
