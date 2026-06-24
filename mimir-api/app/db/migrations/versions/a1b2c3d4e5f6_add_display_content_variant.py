"""add display content_variant column

Revision ID: a1b2c3d4e5f6
Revises: 8ae5e4a6c326
Create Date: 2026-06-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '8ae5e4a6c326'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('display_clients') as batch_op:
        batch_op.add_column(sa.Column('content_variant', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('display_clients') as batch_op:
        batch_op.drop_column('content_variant')
