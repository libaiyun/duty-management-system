"""grant swap permissions to existing system administrators

Revision ID: grant_swap_perms_admin
Revises: add_shift_swap_m4p2
"""

from alembic import op


revision = "grant_swap_perms_admin"
down_revision = "add_shift_swap_m4p2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO sys_role_permission (role_id, permission_id)
        SELECT role.id, permission.id
        FROM sys_role AS role
        JOIN sys_permission AS permission
          ON permission.code IN ('swap:apply:create', 'swap:apply:confirm')
        WHERE role.code = 'system_admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM sys_role_permission
        WHERE role_id IN (SELECT id FROM sys_role WHERE code = 'system_admin')
          AND permission_id IN (
              SELECT id FROM sys_permission
              WHERE code IN ('swap:apply:create', 'swap:apply:confirm')
          )
    """)
