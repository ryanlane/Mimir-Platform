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

"""add scenes.rotation_index

Persisted round-robin cursor for multi-source scenes: the index into
`channels` that the NEXT refresh should use. Lives in the DB (not an
in-memory dict) so rotation position survives a server restart.

Revision ID: a3b4c5d6e7f8
Revises: f7a8b9c0d1e2
Create Date: 2026-07-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a3b4c5d6e7f8'
down_revision: str | Sequence[str] | None = 'f7a8b9c0d1e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c['name'] == 'rotation_index' for c in inspector.get_columns('scenes'))


def upgrade() -> None:
    if _column_exists():
        return
    op.add_column(
        'scenes',
        sa.Column('rotation_index', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    if _column_exists():
        op.drop_column('scenes', 'rotation_index')
