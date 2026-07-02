from pathlib import Path

import pytest

from app.core.config import AppEnvironment, ConfigError, Settings, load_settings
from app.main import create_app


def test_load_settings_uses_dev_defaults() -> None:
    settings = load_settings({})

    assert settings.app_env == AppEnvironment.DEV
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.jwt_secret_key == "dev-only-change-me"
    assert settings.jwt_access_token_expire_minutes == 30
    assert settings.jwt_refresh_token_expire_minutes == 10080
    assert settings.file_storage_dir == Path("data/files")
    assert settings.export_dir == Path("data/files/export")
    assert settings.backup_dir == Path("data/files/backup")


def test_load_settings_reads_environment_overrides() -> None:
    settings = load_settings(
        {
            "DUTY_APP_ENV": "test",
            "DUTY_DATABASE_URL": "postgresql+psycopg://test:test@db:5432/test_db",
            "DUTY_REDIS_URL": "redis://redis:6379/1",
            "DUTY_JWT_SECRET_KEY": "test-secret",
            "DUTY_JWT_ALGORITHM": "HS512",
            "DUTY_JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "15",
            "DUTY_JWT_REFRESH_TOKEN_EXPIRE_MINUTES": "1440",
            "DUTY_FILE_STORAGE_DIR": "/tmp/files",
            "DUTY_EXPORT_DIR": "/tmp/files/export",
            "DUTY_BACKUP_DIR": "/tmp/files/backup",
        }
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


def test_load_settings_rejects_invalid_environment() -> None:
    with pytest.raises(ConfigError, match="DUTY_APP_ENV must be one of"):
        load_settings({"DUTY_APP_ENV": "staging"})


def test_load_settings_rejects_invalid_positive_integer() -> None:
    with pytest.raises(
        ConfigError,
        match="DUTY_JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer",
    ):
        load_settings({"DUTY_JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "0"})


def test_load_settings_reports_missing_production_keys() -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_settings({"DUTY_APP_ENV": "prod"})

    message = str(exc_info.value)
    assert "Production config is missing required env vars" in message
    assert "DUTY_DATABASE_URL" in message
    assert "DUTY_REDIS_URL" in message
    assert "DUTY_JWT_SECRET_KEY" in message
    assert "DUTY_FILE_STORAGE_DIR" in message
    assert "DUTY_EXPORT_DIR" in message
    assert "DUTY_BACKUP_DIR" in message


def test_load_settings_rejects_insecure_production_jwt_secret() -> None:
    with pytest.raises(
        ConfigError,
        match="DUTY_JWT_SECRET_KEY must be changed for production",
    ):
        load_settings(
            {
                "DUTY_APP_ENV": "prod",
                "DUTY_DATABASE_URL": "postgresql+psycopg://prod:prod@db:5432/prod_db",
                "DUTY_REDIS_URL": "redis://redis:6379/0",
                "DUTY_JWT_SECRET_KEY": "change-me",
                "DUTY_FILE_STORAGE_DIR": "/data/files",
                "DUTY_EXPORT_DIR": "/data/files/export",
                "DUTY_BACKUP_DIR": "/data/files/backup",
            }
        )


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
