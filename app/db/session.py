from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Optimized for hosted Supabase PostgreSQL (direct or pooled connections)
# pool_pre_ping: tests liveness before issuing query
# pool_recycle: recycles idle connections before cloud NAT/Supabase drop them (30 mins)
# connect_timeout: 3s fast-fail on unreachable DB hosts to prevent blocking thread execution
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    echo=False,
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency generator for obtaining database sessions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
