"""add export task

Revision ID: add_export_task_m3p3
Revises: add_schedule_change_log
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_export_task_m3p3"
down_revision: str | None = "add_schedule_change_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_task",
        sa.Column("org_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_export_task_org_created", "export_task", ["org_unit_id", "created_at"])
    op.create_index("ix_export_task_status", "export_task", ["status"])


def downgrade() -> None:
    op.drop_index("ix_export_task_status", table_name="export_task")
    op.drop_index("ix_export_task_org_created", table_name="export_task")
    op.drop_table("export_task")
