"""store final schedule baselines and personnel change ledger

Revision ID: final_schedule_ledger_m5
Revises: grant_swap_permissions
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "final_schedule_ledger_m5"
down_revision: str | None = "grant_swap_perms_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_shift_baseline_person",
        sa.Column("schedule_shift_id", sa.BigInteger(), nullable=False),
        sa.Column("person_id", sa.BigInteger(), nullable=False),
        sa.Column("position_no", sa.Integer(), nullable=False),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schedule_shift_id"], ["schedule_shift.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], ondelete="RESTRICT"),
    )
    op.create_index("uq_schedule_shift_baseline_position", "schedule_shift_baseline_person", ["schedule_shift_id", "position_no"], unique=True)
    # Prefer the legacy projection's original person: it survives a swap while
    # schedule_shift_person contains the already-adjusted final person.
    op.execute("""
        INSERT INTO schedule_shift_baseline_person
          (schedule_shift_id, person_id, position_no, created_at, updated_at, version)
        SELECT schedule_shift_id, original_person_id,
               ROW_NUMBER() OVER (PARTITION BY schedule_shift_id ORDER BY id),
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1
        FROM actual_duty
    """)
    # Unpublished shifts have no legacy projection; their generated personnel is
    # necessarily also their original baseline.
    op.execute("""
        INSERT INTO schedule_shift_baseline_person
          (schedule_shift_id, person_id, position_no, created_at, updated_at, version)
        SELECT person.schedule_shift_id, person.person_id, person.position_no,
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1
        FROM schedule_shift_person AS person
        WHERE NOT EXISTS (
            SELECT 1
            FROM schedule_shift_baseline_person AS baseline
            WHERE baseline.schedule_shift_id = person.schedule_shift_id
        )
    """)
    op.create_table(
        "duty_change_ledger",
        sa.Column("schedule_shift_id", sa.BigInteger(), nullable=False),
        sa.Column("original_person_id", sa.BigInteger(), nullable=False),
        sa.Column("before_person_id", sa.BigInteger(), nullable=False),
        sa.Column("after_person_id", sa.BigInteger(), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("source_biz_no", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schedule_shift_id"], ["schedule_shift.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_person_id"], ["person.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["before_person_id"], ["person.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["after_person_id"], ["person.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_duty_change_ledger_shift", "duty_change_ledger", ["schedule_shift_id"])
    op.create_index("ix_duty_change_ledger_type", "duty_change_ledger", ["change_type"])
    op.create_index("ix_duty_change_ledger_original_person", "duty_change_ledger", ["original_person_id"])
    op.create_index("ix_duty_change_ledger_before_person", "duty_change_ledger", ["before_person_id"])
    op.create_index("ix_duty_change_ledger_after_person", "duty_change_ledger", ["after_person_id"])


def downgrade() -> None:
    op.drop_table("duty_change_ledger")
    op.drop_table("schedule_shift_baseline_person")
