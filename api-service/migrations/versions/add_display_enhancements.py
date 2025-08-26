"""Add hostname, webhook, and Redis distribution fields to display_clients

Revision ID: add_display_enhancements
Revises: previous_migration
Create Date: 2025-08-26

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_display_enhancements'
down_revision = None  # Replace with actual previous revision
branch_labels = None
depends_on = None

def upgrade():
    """Add new fields to support enhanced display client capabilities"""
    
    # Add hostname field
    op.add_column('display_clients', sa.Column('hostname', sa.String(), nullable=True))
    
    # Add webhook support
    op.add_column('display_clients', sa.Column('webhook_port', sa.Integer(), nullable=True))
    
    # Add Redis distribution capabilities
    op.add_column('display_clients', sa.Column('redis_distribution', sa.Boolean(), default=False, nullable=True))
    op.add_column('display_clients', sa.Column('content_claiming', sa.Boolean(), default=False, nullable=True))

def downgrade():
    """Remove the enhanced display client fields"""
    
    op.drop_column('display_clients', 'content_claiming')
    op.drop_column('display_clients', 'redis_distribution')
    op.drop_column('display_clients', 'webhook_port')
    op.drop_column('display_clients', 'hostname')
