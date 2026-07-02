from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, load_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    resolved_settings = settings or load_settings()
    return create_engine(
        resolved_settings.database_url,
        pool_pre_ping=True,
    )


engine = create_db_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
