"""add shift swaps for M4-P2

Revision ID: add_shift_swap_m4p2
Revises: add_approval_tasks_m4p1
"""

from alembic import op
import sqlalchemy as sa

revision = "add_shift_swap_m4p2"
down_revision = "add_approval_tasks_m4p1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shift_swap",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("biz_no", sa.String(64), nullable=False, unique=True),
        sa.Column("swap_type", sa.String(32), nullable=False),
        sa.Column("applicant_person_id", sa.BigInteger(), sa.ForeignKey("person.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_shift_id", sa.BigInteger(), sa.ForeignKey("schedule_shift.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_person_id", sa.BigInteger(), sa.ForeignKey("person.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_shift_id", sa.BigInteger(), sa.ForeignKey("schedule_shift.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True), sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_shift_swap_applicant_status", "shift_swap", ["applicant_person_id", "status"])
    op.create_index("ix_shift_swap_target_status", "shift_swap", ["target_person_id", "status"])
    op.execute("""
        INSERT INTO sys_permission (code, name, type, status, created_at, updated_at, version)
        VALUES ('swap:apply:create', '发起换班', 'api', 'enabled', now(), now(), 1),
               ('swap:apply:confirm', '确认换班', 'api', 'enabled', now(), now(), 1)
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO sys_role_permission (role_id, permission_id)
        SELECT role.id, permission.id FROM sys_role role CROSS JOIN sys_permission permission
        WHERE role.code IN ('duty_operator', 'deputy_director', 'room_director')
          AND permission.code IN ('swap:apply:create', 'swap:apply:confirm')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_shift_swap_target_status", table_name="shift_swap")
    op.drop_index("ix_shift_swap_applicant_status", table_name="shift_swap")
    op.drop_table("shift_swap")
