from collections.abc import Generator
from os import environ
from pathlib import Path
from re import sub
from uuid import uuid4

import app.models  # noqa: F401 — ensure models are registered in Base.metadata
import pytest
from alembic import command
from alembic.config import Config
from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

TEST_ADMIN_DATABASE_URL_ENV = "DUTY_TEST_ADMIN_DATABASE_URL"
DEFAULT_TEST_ADMIN_DATABASE_URL = "postgresql+psycopg://duty_test:duty_test@db:5432/postgres"


def _database_name(suffix: str) -> str:
    return f"duty_system_test_{sub(r'[^a-zA-Z0-9_]', '_', suffix)}"


def _create_database(engine: Engine, database_name: str) -> None:
    with engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))


def _drop_database(engine: Engine, database_name: str) -> None:
    with engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))


def _upgrade_database(database_url: str) -> None:
    alembic_config = Config("alembic.ini")
    alembic_config.attributes["database_url"] = database_url
    command.upgrade(alembic_config, "head")


def _clear_application_data(engine: Engine) -> None:
    table_names = ", ".join(f'"{table_name}"' for table_name in Base.metadata.tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


def _reset_sequences(engine: Engine) -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        sequence_names = connection.scalars(text("""
            SELECT sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema = 'public'
        """)).all()
        for sequence_name in sequence_names:
            connection.execute(text(f'ALTER SEQUENCE "{sequence_name}" RESTART WITH 1'))


@pytest.fixture(scope="session")
def postgres_admin_url() -> URL:
    return make_url(environ.get(TEST_ADMIN_DATABASE_URL_ENV, DEFAULT_TEST_ADMIN_DATABASE_URL))


@pytest.fixture(scope="session")
def postgres_admin_engine(postgres_admin_url: URL) -> Generator[Engine, None, None]:
    engine = create_engine(postgres_admin_url, isolation_level="AUTOCOMMIT")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def postgres_database_url(
    postgres_admin_engine: Engine,
    postgres_admin_url: URL,
    worker_id: str,
) -> Generator[str, None, None]:
    database_name = _database_name(worker_id)
    _drop_database(postgres_admin_engine, database_name)
    _create_database(postgres_admin_engine, database_name)
    database_url = postgres_admin_url.set(database=database_name).render_as_string(hide_password=False)
    try:
        yield database_url
    finally:
        _drop_database(postgres_admin_engine, database_name)


@pytest.fixture
def empty_postgres_database_url(
    postgres_admin_engine: Engine,
    postgres_admin_url: URL,
) -> Generator[str, None, None]:
    database_name = _database_name(f"migration_{uuid4().hex}")
    _create_database(postgres_admin_engine, database_name)
    database_url = postgres_admin_url.set(database=database_name).render_as_string(hide_password=False)
    try:
        yield database_url
    finally:
        _drop_database(postgres_admin_engine, database_name)


@pytest.fixture(scope="session")
def postgres_engine(postgres_database_url: str) -> Generator[Engine, None, None]:
    _upgrade_database(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _clear_application_data(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def create_tables(postgres_engine: Engine) -> Generator[None, None, None]:
    # The test database is initialized from Alembic migrations, not model metadata.
    yield


@pytest.fixture
def test_settings(postgres_database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        app_env=AppEnvironment.TEST,
        database_url=postgres_database_url,
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
def db_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    _reset_sequences(postgres_engine)
    connection = postgres_engine.connect()
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
        if transaction.is_active:
            transaction.rollback()
        connection.close()
