"""m3_p1_t1_schedule_tables

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-13 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'e3f4a5b6c7d8'
down_revision: str | None = 'd2e3f4a5b6c7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('monthly_schedule',
        sa.Column('org_unit_id', sa.BigInteger(), nullable=False),
        sa.Column('year_month', sa.String(length=7), nullable=False),
        sa.Column('rule_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('remark', sa.String(length=500), nullable=True),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['org_unit_id'], ['org_unit.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rule_id'], ['shift_rule.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_monthly_schedule_org_month',
        'monthly_schedule',
        ['org_unit_id', 'year_month'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
        sqlite_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table('schedule_day',
        sa.Column('schedule_id', sa.BigInteger(), nullable=False),
        sa.Column('duty_date', sa.Date(), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('is_legal_holiday', sa.Boolean(), nullable=False),
        sa.Column('holiday_name', sa.String(length=64), nullable=True),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['schedule_id'], ['monthly_schedule.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schedule_day_duty_date', 'schedule_day', ['duty_date'])
    op.create_index('ix_schedule_day_schedule_id', 'schedule_day', ['schedule_id'])

    op.create_table('schedule_shift',
        sa.Column('schedule_day_id', sa.BigInteger(), nullable=False),
        sa.Column('shift_def_id', sa.BigInteger(), nullable=False),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['schedule_day_id'], ['schedule_day.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shift_def_id'], ['shift_def.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schedule_shift_day', 'schedule_shift', ['schedule_day_id'])

    op.create_table('schedule_shift_person',
        sa.Column('schedule_shift_id', sa.BigInteger(), nullable=False),
        sa.Column('person_id', sa.BigInteger(), nullable=False),
        sa.Column('position_no', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('remark', sa.String(length=255), nullable=True),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['schedule_shift_id'], ['schedule_shift.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['person.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schedule_shift_person_shift', 'schedule_shift_person', ['schedule_shift_id'])


def downgrade() -> None:
    op.drop_index('ix_schedule_shift_person_shift', table_name='schedule_shift_person')
    op.drop_table('schedule_shift_person')
    op.drop_index('ix_schedule_shift_day', table_name='schedule_shift')
    op.drop_table('schedule_shift')
    op.drop_index('ix_schedule_day_schedule_id', table_name='schedule_day')
    op.drop_index('ix_schedule_day_duty_date', table_name='schedule_day')
    op.drop_table('schedule_day')
    op.drop_index('uq_monthly_schedule_org_month', table_name='monthly_schedule')
    op.drop_table('monthly_schedule')
