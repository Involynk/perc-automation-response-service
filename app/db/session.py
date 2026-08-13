from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
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
