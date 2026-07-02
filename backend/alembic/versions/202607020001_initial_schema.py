"""initial schema

Revision ID: 202607020001
Revises:
Create Date: 2026-07-02 00:01:00
"""

from collections.abc import Sequence

revision: str = "202607020001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
