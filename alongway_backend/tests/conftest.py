"""
Pytest configuration and shared fixtures.
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.models import Base


@pytest.fixture(scope="session")
def test_database():
    """Create test database."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_database):
    """Create test session."""
    TestingSessionLocal = sessionmaker(bind=test_database)
    session = TestingSessionLocal()
    yield session
    session.close()
