"""Shared pytest fixtures for API tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401 -- register all models with Base.metadata
from backend.config import settings
from backend.database import Base, get_db
from backend.main import app

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture(autouse=True)
def _email_log_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let auth emails succeed via DEBUG log without Resend/SMTP in tests."""

    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr("backend.services.email_service.settings.debug", True)
    monkeypatch.setattr("backend.services.auth_email_service.settings.debug", True)
    monkeypatch.setattr("backend.routes.auth.settings.debug", True)


@pytest.fixture
def database_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory database session for each test."""

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    session = testing_session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(database_session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI test client with the database dependency overridden."""

    def override_get_db() -> Generator[Session, None, None]:
        yield database_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
