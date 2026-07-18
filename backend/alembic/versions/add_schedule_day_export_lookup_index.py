"""add schedule-day export lookup index

Revision ID: add_schedule_day_export_lookup
Revises: add_export_task_m3p3
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "add_schedule_day_export_lookup"
down_revision: str | None = "add_export_task_m3p3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_schedule_day_schedule_date_lookup", "schedule_day", ["schedule_id", "duty_date"])


def downgrade() -> None:
    op.drop_index("ix_schedule_day_schedule_date_lookup", table_name="schedule_day")
