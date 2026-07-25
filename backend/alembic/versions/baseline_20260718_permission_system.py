"""Final baseline with configurable RBAC and account direct grants.

Revision ID: baseline_20260718
Revises:
"""

import os
from collections.abc import Sequence

import app.models  # noqa: F401
from alembic import op
from app.db.base import Base
from app.services.auth import create_user, seed_permission_system
from sqlalchemy.orm import Session

revision: str = "baseline_20260718"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    session = Session(bind=bind)
    try:
        seed_permission_system(session)
        create_user(
            session,
            os.environ.get("DUTY_INITIAL_SUPERUSER", "superadmin"),
            os.environ.get("DUTY_INITIAL_SUPERUSER_PASSWORD", "ChangeMeNow!"),
            "超级管理员",
            is_superuser=True,
        )
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
