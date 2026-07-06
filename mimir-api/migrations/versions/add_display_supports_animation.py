"""Add supports_animation capability flag to display_clients

Displays report whether their panel can play animated content (WebP/GIF
loops). NULL means unknown — the client predates the capability flag —
and channels treat unknown as "don't downgrade".

Revision ID: add_display_supports_animation
Revises: add_scene_push_fields
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_display_supports_animation'
down_revision = 'add_scene_push_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('display_clients', sa.Column('supports_animation', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('display_clients', 'supports_animation')
