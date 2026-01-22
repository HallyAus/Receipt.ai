"""Pytest configuration and fixtures."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-bytes-long"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.core.database import Base


@pytest.fixture
def sync_engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def sync_session(sync_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=sync_engine)
    session = Session()
    yield session
    session.close()
