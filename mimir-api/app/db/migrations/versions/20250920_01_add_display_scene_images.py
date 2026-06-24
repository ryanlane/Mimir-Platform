# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Add display_scene_images table

Revision ID: 20250920_add_display_scene_img
Revises: 9f3f58276f60
Create Date: 2025-09-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# NOTE: Keep revision IDs <= 32 chars (Alembic's default version table column is VARCHAR(32)).
revision: str = '20250920_add_display_scene_img'
# Depends on initial full schema migration
down_revision: str | Sequence[str] | None = '9f3f58276f60'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    """Add new persistent tracking table for distributed images per display & scene."""
    op.create_table(
        'display_scene_images',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('display_id', sa.String(), nullable=False, index=True),
        sa.Column('scene_id', sa.String(), nullable=False, index=True),
        sa.Column('subchannel_id', sa.String(), nullable=True, index=True),
        sa.Column('assignment_id', sa.String(), nullable=False, index=True),
        sa.Column('image_url', sa.String(), nullable=False),
        sa.Column('stored_local_path', sa.String(), nullable=True),
        sa.Column('thumbnail_path', sa.String(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(), nullable=True),
        sa.Column('hash', sa.String(), nullable=True, index=True),
        sa.Column('source', sa.String(), nullable=False, server_default='distribution', index=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_display_scene_images_display_scene', 'display_scene_images', ['display_id', 'scene_id'], unique=False)
    op.create_index('ix_display_scene_images_scene_created', 'display_scene_images', ['scene_id', 'created_at'], unique=False)
    op.create_index('ix_display_scene_images_display_created', 'display_scene_images', ['display_id', 'created_at'], unique=False)

def downgrade() -> None:
    """Remove table if rolling back."""
    op.drop_index('ix_display_scene_images_display_created', table_name='display_scene_images')
    op.drop_index('ix_display_scene_images_scene_created', table_name='display_scene_images')
    op.drop_index('ix_display_scene_images_display_scene', table_name='display_scene_images')
    op.drop_table('display_scene_images')
