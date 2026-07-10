from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

import app.models  # noqa: F401 — ensure models are registered in Base.metadata


@pytest.fixture
def create_tables(sqlite_engine: Engine) -> Generator[None, None, None]:
    Base.metadata.create_all(sqlite_engine)
    yield


@pytest.fixture
def test_settings(sqlite_database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        app_env=AppEnvironment.TEST,
        database_url=sqlite_database_url,
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_minutes=10080,
        file_storage_dir=tmp_path / "files",
        export_dir=tmp_path / "files" / "export",
        backup_dir=tmp_path / "files" / "backup",
    )


@pytest.fixture
def app(test_settings: Settings, db_session: Session) -> FastAPI:
    app = create_app(settings=test_settings)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def api_client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


@pytest.fixture
def api_client_no_raise(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def sqlite_database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def sqlite_engine(sqlite_database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(sqlite_database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(sqlite_engine: Engine) -> Generator[Session, None, None]:
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
