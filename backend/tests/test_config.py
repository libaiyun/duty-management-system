from pathlib import Path

import pytest
from app.core.config import AppEnvironment, ConfigError, Settings, load_settings
from app.main import create_app
from pydantic import ValidationError


def test_settings_uses_dev_defaults() -> None:
    settings = Settings()

    assert settings.app_env == AppEnvironment.DEV
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url.startswith("redis://")
    assert settings.jwt_secret_key == "dev-only-change-me"
    assert settings.jwt_access_token_expire_minutes == 30
    assert settings.jwt_refresh_token_expire_minutes == 10080
    assert settings.file_storage_dir == Path("data/files")
    assert settings.export_dir == Path("data/files/export")
    assert settings.backup_dir == Path("data/files/backup")


def test_settings_reads_constructor_overrides() -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://test:test@db:5432/test_db",
        redis_url="redis://redis:6379/1",
        jwt_secret_key="test-secret",
        jwt_algorithm="HS512",
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_minutes=1440,
        file_storage_dir=Path("/tmp/files"),
        export_dir=Path("/tmp/files/export"),
        backup_dir=Path("/tmp/files/backup"),
    )

    assert settings.app_env == AppEnvironment.TEST
    assert settings.database_url == "postgresql+psycopg://test:test@db:5432/test_db"
    assert settings.redis_url == "redis://redis:6379/1"
    assert settings.jwt_secret_key == "test-secret"
    assert settings.jwt_algorithm == "HS512"
    assert settings.jwt_access_token_expire_minutes == 15
    assert settings.jwt_refresh_token_expire_minutes == 1440
    assert settings.file_storage_dir == Path("/tmp/files")
    assert settings.export_dir == Path("/tmp/files/export")
    assert settings.backup_dir == Path("/tmp/files/backup")


def test_settings_rejects_invalid_environment() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(app_env="staging")
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "staging" in str(errors[0]["msg"]).lower() or errors[0]["type"] in (
        "enum",
        "value_error",
    )


def test_settings_rejects_invalid_positive_integer() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_access_token_expire_minutes=0)
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "positive integer" in str(errors[0]["msg"]).lower()


def test_settings_rejects_missing_production_keys() -> None:
    with pytest.raises(ValidationError, match="missing required env vars"):
        Settings(app_env=AppEnvironment.PROD)


def test_settings_rejects_insecure_production_jwt_secret() -> None:
    with pytest.raises(
        ValidationError,
        match="DUTY_JWT_SECRET_KEY must be changed",
    ):
        Settings(
            app_env=AppEnvironment.PROD,
            database_url="postgresql+psycopg://prod:prod@db:5432/prod_db",
            redis_url="redis://redis:6379/0",
            jwt_secret_key="change-me",
            file_storage_dir="/data/files",
            export_dir="/data/files/export",
            backup_dir="/data/files/backup",
        )


def test_load_settings_wraps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUTY_APP_ENV", "prod")
    with pytest.raises(ConfigError):
        load_settings()


def test_create_app_attaches_settings_to_state() -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://test:test@db:5432/test_db",
        redis_url="redis://redis:6379/1",
        jwt_secret_key="test-secret",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_minutes=10080,
        file_storage_dir=Path("tmp/files"),
        export_dir=Path("tmp/files/export"),
        backup_dir=Path("tmp/files/backup"),
    )

    app = create_app(settings=settings)

    assert app.state.settings == settings
