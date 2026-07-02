from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Integer, String, create_engine, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import create_db_engine


class LocalBase(DeclarativeBase):
    pass


class SampleRecord(LocalBase):
    __tablename__ = "sample_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


def test_create_db_engine_uses_settings_database_url() -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_minutes=10080,
        file_storage_dir=Path("tmp/files"),
        export_dir=Path("tmp/files/export"),
        backup_dir=Path("tmp/files/backup"),
    )

    engine = create_db_engine(settings)
    try:
        assert str(engine.url) == "sqlite:///:memory:"
    finally:
        engine.dispose()


def test_create_db_engine_supports_postgresql_dialect() -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://user:pass@localhost:5432/duty_system",
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_minutes=10080,
        file_storage_dir=Path("tmp/files"),
        export_dir=Path("tmp/files/export"),
        backup_dir=Path("tmp/files/backup"),
    )

    engine = create_db_engine(settings)
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.driver == "psycopg"
    finally:
        engine.dispose()


def test_test_models_do_not_pollute_application_metadata() -> None:
    assert "sample_record" not in Base.metadata.tables
    assert "sample_record" in LocalBase.metadata.tables


def test_test_transaction_rolls_back_data(sqlite_engine) -> None:
    LocalBase.metadata.create_all(bind=sqlite_engine)
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    try:
        session.add(SampleRecord(name="temporary"))
        session.flush()

        rows = session.scalars(select(SampleRecord)).all()
        assert [row.name for row in rows] == ["temporary"]
    finally:
        session.close()
        transaction.rollback()
        connection.close()

    verification_session_factory = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    with verification_session_factory() as verification_session:
        rows = verification_session.scalars(select(SampleRecord)).all()

    assert rows == []


def test_alembic_upgrade_head_creates_version_table(
    monkeypatch,
    sqlite_database_url: str,
) -> None:
    monkeypatch.setenv("DUTY_DATABASE_URL", sqlite_database_url)
    alembic_config = Config("alembic.ini")

    command.upgrade(alembic_config, "head")

    engine = create_engine(sqlite_database_url)
    try:
        inspector = inspect(engine)
        assert "alembic_version" in inspector.get_table_names()
    finally:
        engine.dispose()
