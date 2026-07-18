"""add actual duty and schedule editing support

Revision ID: add_actual_duty_m3p2
Revises: add_schedule_day_date_unique
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_actual_duty_m3p2"
down_revision: str | None = "add_shift_rule_superseded_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actual_duty",
        sa.Column("org_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("schedule_shift_id", sa.BigInteger(), nullable=False),
        sa.Column("original_person_id", sa.BigInteger(), nullable=False),
        sa.Column("actual_person_id", sa.BigInteger(), nullable=False),
        sa.Column("duty_date", sa.Date(), nullable=False),
        sa.Column("shift_def_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.BigInteger(), nullable=True),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["schedule_shift_id"], ["schedule_shift.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["original_person_id"], ["person.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actual_person_id"], ["person.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shift_def_id"], ["shift_def.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_actual_duty_org_date", "actual_duty", ["org_unit_id", "duty_date"])
    op.create_index("ix_actual_duty_person_date", "actual_duty", ["actual_person_id", "duty_date"])
    op.create_index("ix_actual_duty_shift_date", "actual_duty", ["shift_def_id", "duty_date"])
    op.create_index("uq_actual_duty_shift_original", "actual_duty", ["schedule_shift_id", "original_person_id"], unique=True)


def downgrade() -> None:
    op.drop_table("actual_duty")
