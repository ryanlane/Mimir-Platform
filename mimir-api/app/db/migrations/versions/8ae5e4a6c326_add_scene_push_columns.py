"""add scene push columns

Revision ID: 8ae5e4a6c326
Revises: 20250920_add_display_scene_img
Create Date: 2025-09-21 15:22:38.232513

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '8ae5e4a6c326'
down_revision: str | Sequence[str] | None = '20250920_add_display_scene_img'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
