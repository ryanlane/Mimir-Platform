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

"""add file_sources table

File Sources are user-configured media roots (local bind-mounted paths or
SMB shares) browsable from the web UI and shared by every file-consuming
channel plugin. Local sources are constrained to the generic host media
mount; SMB credentials live in the config JSON.

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-07-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f7a8b9c0d1e2'
down_revision: str | Sequence[str] | None = 'e5f6a7b8c9d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists() -> bool:
    inspector = sa.inspect(op.get_bind())
    return 'file_sources' in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists():
        return
    op.create_table(
        'file_sources',
        sa.Column('id', sa.String(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False, index=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), index=True),
        sa.Column('updated_at', sa.DateTime()),
    )


def downgrade() -> None:
    if _table_exists():
        op.drop_table('file_sources')
