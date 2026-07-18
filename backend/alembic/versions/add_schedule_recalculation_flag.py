"""mark historical months requiring recalculation

Revision ID: schedule_recalc_flag_m5
Revises: drop_actual_duty_m5
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "schedule_recalc_flag_m5"
down_revision: str | None = "drop_actual_duty_m5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_recalculation_flag",
        sa.Column("org_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("org_unit_id", "year_month", name="uq_schedule_recalculation_flag_month"),
    )
    op.create_index("ix_schedule_recalculation_flag_status", "schedule_recalculation_flag", ["status"])


def downgrade() -> None:
    op.drop_table("schedule_recalculation_flag")
