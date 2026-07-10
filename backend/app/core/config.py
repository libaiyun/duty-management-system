from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from os import environ
from pathlib import Path


class AppEnvironment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    app_env: AppEnvironment
    database_url: str
    redis_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int
    jwt_refresh_token_expire_minutes: int
    file_storage_dir: Path
    export_dir: Path
    backup_dir: Path


DEFAULT_VALUES = {
    "DUTY_DATABASE_URL": "postgresql+psycopg://duty_app:duty_app@localhost:5432/duty_system",
    "DUTY_REDIS_URL": "redis://localhost:6379/0",
    "DUTY_JWT_SECRET_KEY": "dev-only-change-me",
    "DUTY_JWT_ALGORITHM": "HS256",
    "DUTY_JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "30",
    "DUTY_JWT_REFRESH_TOKEN_EXPIRE_MINUTES": "10080",
    "DUTY_FILE_STORAGE_DIR": "data/files",
    "DUTY_EXPORT_DIR": "data/files/export",
    "DUTY_BACKUP_DIR": "data/files/backup",
}

PRODUCTION_REQUIRED_KEYS = (
    "DUTY_DATABASE_URL",
    "DUTY_REDIS_URL",
    "DUTY_JWT_SECRET_KEY",
    "DUTY_FILE_STORAGE_DIR",
    "DUTY_EXPORT_DIR",
    "DUTY_BACKUP_DIR",
)

INSECURE_JWT_SECRET_VALUES = {
    "change-me",
    "dev-only-change-me",
}


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = env if env is not None else environ
    app_env = _read_app_environment(source)
    if app_env == AppEnvironment.PROD:
        _ensure_production_keys(source)

    return Settings(
        app_env=app_env,
        database_url=_read_string(source, "DUTY_DATABASE_URL"),
        redis_url=_read_string(source, "DUTY_REDIS_URL"),
        jwt_secret_key=_read_string(source, "DUTY_JWT_SECRET_KEY"),
        jwt_algorithm=_read_string(source, "DUTY_JWT_ALGORITHM"),
        jwt_access_token_expire_minutes=_read_positive_int(
            source,
            "DUTY_JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
        jwt_refresh_token_expire_minutes=_read_positive_int(
            source,
            "DUTY_JWT_REFRESH_TOKEN_EXPIRE_MINUTES",
        ),
        file_storage_dir=_read_path(source, "DUTY_FILE_STORAGE_DIR"),
        export_dir=_read_path(source, "DUTY_EXPORT_DIR"),
        backup_dir=_read_path(source, "DUTY_BACKUP_DIR"),
    )


def _read_app_environment(source: Mapping[str, str]) -> AppEnvironment:
    raw_value = source.get("DUTY_APP_ENV", AppEnvironment.DEV.value).strip().lower()
    try:
        return AppEnvironment(raw_value)  # type: ignore[arg-type]
    except ValueError as exc:
        allowed = ", ".join(item.value for item in AppEnvironment)
        raise ConfigError(f"DUTY_APP_ENV must be one of: {allowed}") from exc


def _ensure_production_keys(source: Mapping[str, str]) -> None:
    missing_keys = [
        key for key in PRODUCTION_REQUIRED_KEYS if not source.get(key) or source[key].strip() == DEFAULT_VALUES.get(key)
    ]
    if missing_keys:
        joined_keys = ", ".join(missing_keys)
        raise ConfigError(f"Production config is missing required env vars: {joined_keys}")

    jwt_secret = source["DUTY_JWT_SECRET_KEY"].strip()
    if jwt_secret in INSECURE_JWT_SECRET_VALUES:
        raise ConfigError("DUTY_JWT_SECRET_KEY must be changed for production")


def _read_string(source: Mapping[str, str], key: str) -> str:
    value = source.get(key, DEFAULT_VALUES[key]).strip()
    if not value:
        raise ConfigError(f"{key} must not be empty")
    return value


def _read_positive_int(source: Mapping[str, str], key: str) -> int:
    raw_value = _read_string(source, key)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a positive integer") from exc
    if value <= 0:
        raise ConfigError(f"{key} must be a positive integer")
    return value


def _read_path(source: Mapping[str, str], key: str) -> Path:
    return Path(_read_string(source, key))
