"""add immutable manual schedule adjustment log

Revision ID: add_schedule_change_log
Revises: add_actual_duty_m3p2
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add_schedule_change_log"
down_revision: str | None = "add_actual_duty_m3p2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_change_log",
        sa.Column("schedule_id", sa.BigInteger(), nullable=False),
        sa.Column("schedule_shift_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("before_person_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_person_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["monthly_schedule.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_shift_id"], ["schedule_shift.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_schedule_change_log_schedule_shift", "schedule_change_log", ["schedule_id", "schedule_shift_id"])


def downgrade() -> None:
    op.drop_table("schedule_change_log")
