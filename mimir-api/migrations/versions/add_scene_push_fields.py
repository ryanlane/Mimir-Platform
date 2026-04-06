"""Add scene push update strategy fields

Revision ID: add_scene_push_fields
Revises: add_display_enhancements
Create Date: 2025-09-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_scene_push_fields'
down_revision = 'add_display_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    """Add update_strategy and push_fallback_poll_seconds to scenes"""
    # Add columns (nullable first for backfill safety)
    op.add_column('scenes', sa.Column('update_strategy', sa.String(), nullable=True))
    op.add_column('scenes', sa.Column('push_fallback_poll_seconds', sa.Integer(), nullable=True))

    # Backfill existing rows to default 'scheduler'
    op.execute("UPDATE scenes SET update_strategy = 'scheduler' WHERE update_strategy IS NULL")

    # Make update_strategy non-null moving forward by altering (some DBs require separate step; keep nullable for sqlite compatibility)
    # If targeting Postgres you could uncomment next line:
    # op.alter_column('scenes', 'update_strategy', existing_type=sa.String(), nullable=False)

    # Create index (if not auto-created via SQLAlchemy model sync elsewhere)
    op.create_index('ix_scenes_update_strategy', 'scenes', ['update_strategy'], unique=False)


def downgrade():
    """Remove scene push update strategy fields"""
    # Drop index then columns
    try:
        op.drop_index('ix_scenes_update_strategy', table_name='scenes')
    except Exception:
        pass
    op.drop_column('scenes', 'push_fallback_poll_seconds')
    op.drop_column('scenes', 'update_strategy')
