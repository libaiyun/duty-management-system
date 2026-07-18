"""add approval tasks and records

Revision ID: add_approval_tasks_m4p1
Revises: add_schedule_day_export_lookup
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_approval_tasks_m4p1"
down_revision: str | None = "add_schedule_day_export_lookup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "approval_task",
        sa.Column("org_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("biz_type", sa.String(length=32), nullable=False),
        sa.Column("biz_id", sa.BigInteger(), nullable=False),
        sa.Column("node_code", sa.String(length=64), nullable=False),
        sa.Column("assignee_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["org_unit_id"], ["org_unit.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["sys_user.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_approval_task_assignee_status", "approval_task", ["assignee_user_id", "status"])
    op.create_index("ix_approval_task_org_status", "approval_task", ["org_unit_id", "status"])
    op.create_index("ix_approval_task_org_status_arrived", "approval_task", ["org_unit_id", "status", "arrived_at"])
    op.create_table(
        "approval_record",
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("biz_type", sa.String(length=32), nullable=False),
        sa.Column("biz_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("operator_user_id", sa.BigInteger(), nullable=False),
        sa.Column("opinion", sa.String(length=500), nullable=True),
        sa.Column("operated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_json", sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"), nullable=False),
        *_base_columns(),
        sa.ForeignKeyConstraint(["task_id"], ["approval_task.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["sys_user.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_approval_record_task_operated", "approval_record", ["task_id", "operated_at"])
    op.execute("""
        INSERT INTO sys_role_permission (role_id, permission_id)
        SELECT role.id, permission.id
        FROM sys_role AS role
        JOIN sys_permission AS permission ON permission.code = 'approval:record:view_done'
        WHERE role.code IN ('duty_operator', 'maintenance')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM sys_role_permission
        WHERE permission_id = (SELECT id FROM sys_permission WHERE code = 'approval:record:view_done')
          AND role_id IN (SELECT id FROM sys_role WHERE code IN ('duty_operator', 'maintenance'))
    """)
    op.drop_index("ix_approval_record_task_operated", table_name="approval_record")
    op.drop_table("approval_record")
    op.drop_index("ix_approval_task_org_status_arrived", table_name="approval_task")
    op.drop_index("ix_approval_task_org_status", table_name="approval_task")
    op.drop_index("ix_approval_task_assignee_status", table_name="approval_task")
    op.drop_table("approval_task")
