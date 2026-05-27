from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base


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


def ensure_schema() -> None:
    """Create tables and add lightweight MVP columns when upgrading old DBs."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "pois" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("pois")}
    column_defs = {
        "source_provider": "VARCHAR(50)",
        "source_id": "VARCHAR(100)",
        "source_key": "VARCHAR(100)",
        "category_major": "VARCHAR(100)",
        "category_minor": "VARCHAR(100)",
        "source_type": "VARCHAR(255)",
        "source_typecode": "VARCHAR(50)",
        "phone": "VARCHAR(100)",
        "business_time": "VARCHAR(100)",
        "raw_tags": "TEXT",
    }

    with engine.begin() as conn:
        for column_name, column_type in column_defs.items():
            if column_name not in existing_columns:
                conn.execute(text(f"ALTER TABLE pois ADD COLUMN {column_name} {column_type}"))

        indexes = {
            "ix_pois_source_provider": "source_provider",
            "ix_pois_source_id": "source_id",
            "ix_pois_source_key": "source_key",
            "ix_pois_category_major": "category_major",
            "ix_pois_lng_lat": "longitude, latitude",
        }
        for index_name, index_columns in indexes.items():
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS {index_name} ON pois ({index_columns})")
            )
