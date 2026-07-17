"""add_shift_rule_superseded_status

Revision ID: add_shift_rule_superseded_status
Revises: add_schedule_day_date_unique
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_shift_rule_superseded_status"
down_revision: str | None = "add_schedule_day_date_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing databases may contain multiple published rules. Keep the rule
    # referenced by the room schedule active and retain the others as history.
    op.execute("""
        WITH ranked_rules AS (
            SELECT rule.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY rule.org_unit_id
                       ORDER BY CASE WHEN schedule.rule_id = rule.id THEN 0 ELSE 1 END,
                                rule.updated_at DESC,
                                rule.id DESC
                   ) AS rank_no
            FROM shift_rule AS rule
            LEFT JOIN monthly_schedule AS schedule
              ON schedule.org_unit_id = rule.org_unit_id
             AND schedule.deleted_at IS NULL
            WHERE rule.status = 'published'
              AND rule.deleted_at IS NULL
        )
        UPDATE shift_rule AS rule
        SET status = 'superseded', updated_at = CURRENT_TIMESTAMP
        FROM ranked_rules
        WHERE rule.id = ranked_rules.id AND ranked_rules.rank_no > 1
    """)
    op.create_index(
        "uq_shift_rule_one_published_per_room",
        "shift_rule",
        ["org_unit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published' AND deleted_at IS NULL"),
        sqlite_where=sa.text("status = 'published' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_shift_rule_one_published_per_room", table_name="shift_rule")
