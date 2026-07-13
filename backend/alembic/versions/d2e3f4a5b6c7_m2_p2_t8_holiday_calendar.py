"""m2_p2_t8_holiday_calendar

Revision ID: d2e3f4a5b6c7
Revises: c1f2a3b4d5e6
Create Date: 2026-07-13 08:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa



revision: str = 'd2e3f4a5b6c7'
down_revision: str | None = 'c1f2a3b4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('holiday_calendar',
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('holiday_name', sa.String(length=64), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('is_legal', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('remark', sa.String(length=255), nullable=True),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('holiday_date', name='uq_holiday_calendar_date'),
    )
    op.create_index('ix_holiday_calendar_year', 'holiday_calendar', ['year'])


def downgrade() -> None:
    op.drop_index('ix_holiday_calendar_year', table_name='holiday_calendar')
    op.drop_table('holiday_calendar')
