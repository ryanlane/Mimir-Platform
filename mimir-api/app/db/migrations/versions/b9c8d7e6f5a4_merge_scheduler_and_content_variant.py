"""merge scheduler tables and content_variant branches

Revision ID: b9c8d7e6f5a4
Revises: 3c8b4f7ffefc, a1b2c3d4e5f6
Create Date: 2026-06-24

"""
from collections.abc import Sequence

revision: str = 'b9c8d7e6f5a4'
down_revision: str | Sequence[str] | None = ('3c8b4f7ffefc', 'a1b2c3d4e5f6')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
