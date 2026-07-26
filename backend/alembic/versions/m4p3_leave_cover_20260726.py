"""Create leave requests and cover assignments for M4-P3.

Revision ID: m4p3_leave_cover_20260726
Revises: baseline_20260718
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m4p3_leave_cover_20260726"
down_revision: str | None = "baseline_20260718"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    # The pre-M4 baseline uses ``Base.metadata.create_all``.  A fresh database
    # upgraded with the current code therefore already has these tables, while
    # an existing database stamped at that baseline needs them created here.
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "leave_request" not in existing_tables:
        _create_leave_request()
    if "cover_assignment" not in existing_tables:
        _create_cover_assignment()


def _create_leave_request() -> None:
    op.create_table(
        "leave_request",
        *_base_columns(),
        sa.Column("biz_no", sa.String(length=64), nullable=False, unique=True),
        sa.Column("applicant_person_id", sa.BigInteger(), sa.ForeignKey("person.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("schedule_shift_id", sa.BigInteger(), sa.ForeignKey("schedule_shift.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("leave_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_leave_request_applicant_status", "leave_request", ["applicant_person_id", "status"])
    op.create_index("ix_leave_request_shift_status", "leave_request", ["schedule_shift_id", "status"])


def _create_cover_assignment() -> None:
    op.create_table(
        "cover_assignment",
        *_base_columns(),
        sa.Column("biz_no", sa.String(length=64), nullable=False, unique=True),
        sa.Column("leave_request_id", sa.BigInteger(), sa.ForeignKey("leave_request.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cover_person_id", sa.BigInteger(), sa.ForeignKey("person.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.String(length=500), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cover_assignment_leave_status", "cover_assignment", ["leave_request_id", "status"])
    op.create_index("ix_cover_assignment_person_status", "cover_assignment", ["cover_person_id", "status"])


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "cover_assignment" in existing_tables:
        op.drop_index("ix_cover_assignment_person_status", table_name="cover_assignment")
        op.drop_index("ix_cover_assignment_leave_status", table_name="cover_assignment")
        op.drop_table("cover_assignment")
    if "leave_request" in existing_tables:
        op.drop_index("ix_leave_request_shift_status", table_name="leave_request")
        op.drop_index("ix_leave_request_applicant_status", table_name="leave_request")
        op.drop_table("leave_request")
