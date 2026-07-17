"""repair_published_schedule_status

Revision ID: repair_published_schedule_status
Revises: baseline_20260714
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "repair_published_schedule_status"
down_revision: str | None = "baseline_20260714"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE monthly_schedule AS schedule
        SET status = 'published',
            published_at = COALESCE(schedule.published_at, schedule.generated_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        FROM shift_rule AS rule
        WHERE schedule.rule_id = rule.id
          AND schedule.status = 'draft'
          AND rule.status = 'published'
          AND schedule.deleted_at IS NULL
          AND rule.deleted_at IS NULL
    """)


def downgrade() -> None:
    pass
