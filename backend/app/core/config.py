from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class ConfigError(RuntimeError):
    pass


_PRODUCTION_REQUIRED = {
    "database_url": "DUTY_DATABASE_URL",
    "redis_url": "DUTY_REDIS_URL",
    "jwt_secret_key": "DUTY_JWT_SECRET_KEY",
    "file_storage_dir": "DUTY_FILE_STORAGE_DIR",
    "export_dir": "DUTY_EXPORT_DIR",
    "backup_dir": "DUTY_BACKUP_DIR",
}

INSECURE_JWT_SECRET_VALUES = frozenset({"change-me", "dev-only-change-me"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DUTY_",
        frozen=True,
        extra="ignore",
    )

    app_env: AppEnvironment = AppEnvironment.DEV
    database_url: str = "postgresql+psycopg://duty_app:duty_app@localhost:5432/duty_system"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_minutes: int = 10080
    file_storage_dir: Path = Path("data/files")
    export_dir: Path = Path("data/files/export")
    backup_dir: Path = Path("data/files/backup")

    @field_validator("app_env", mode="before")
    @classmethod
    def _coerce_app_env(cls, v: object) -> str:
        return str(v).strip().lower()

    @field_validator("jwt_access_token_expire_minutes", "jwt_refresh_token_expire_minutes")
    @classmethod
    def _validate_positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be a positive integer")
        return v

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if self.app_env != AppEnvironment.PROD:
            return self

        missing = [
            env_name
            for field_name, env_name in _PRODUCTION_REQUIRED.items()
            if field_name not in self.model_fields_set
        ]
        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(f"Production config is missing required env vars: {joined}")

        if self.jwt_secret_key in INSECURE_JWT_SECRET_VALUES:
            raise ValueError("DUTY_JWT_SECRET_KEY must be changed for production")

        return self


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc
