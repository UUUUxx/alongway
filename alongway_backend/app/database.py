from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    db_url = settings.sqlalchemy_database_url
    
    # For SQLite, add special arguments
    if "sqlite" in db_url:
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    # For PostgreSQL
    return create_engine(db_url, pool_pre_ping=True)


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()

