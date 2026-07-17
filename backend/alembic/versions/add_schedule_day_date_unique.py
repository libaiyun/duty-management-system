"""add_schedule_day_date_unique

Revision ID: add_schedule_day_date_unique
Revises: repair_published_schedule_status
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_schedule_day_date_unique"
down_revision: str | None = "repair_published_schedule_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_schedule_day_schedule_date",
        "schedule_day",
        ["schedule_id", "duty_date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_schedule_day_schedule_date", table_name="schedule_day")
