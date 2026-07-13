"""m2_p2_t6_shift_rule

Revision ID: c1f2a3b4d5e6
Revises: b0a9c8d7e6f5
Create Date: 2026-07-13 06:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa



revision: str = 'c1f2a3b4d5e6'
down_revision: str | None = 'b0a9c8d7e6f5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('shift_rule',
        sa.Column('org_unit_id', sa.BigInteger(), nullable=True),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('station_type', sa.String(length=64), nullable=False),
        sa.Column('persons_per_shift', sa.Integer(), nullable=False),
        sa.Column('rule_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['org_unit_id'], ['org_unit.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_shift_rule_code'),
    )
    op.create_table('shift_rule_item',
        sa.Column('rule_id', sa.BigInteger(), nullable=False),
        sa.Column('group_type', sa.String(length=32), nullable=False),
        sa.Column('sequence_no', sa.Integer(), nullable=False),
        sa.Column('shift_code', sa.String(length=32), nullable=False),
        sa.Column('repeat_count', sa.Integer(), nullable=False),
        sa.Column('remark', sa.String(length=255), nullable=True),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['shift_rule.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shift_rule_item_rule_id', 'shift_rule_item', ['rule_id'])


def downgrade() -> None:
    op.drop_index('ix_shift_rule_item_rule_id', table_name='shift_rule_item')
    op.drop_table('shift_rule_item')
    op.drop_table('shift_rule')
