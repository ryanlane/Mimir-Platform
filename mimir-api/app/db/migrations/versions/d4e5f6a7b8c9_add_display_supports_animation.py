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

"""add display_clients supports_animation column

Displays report whether their panel can play animated content (WebP/GIF
loops). NULL means unknown — the client predates the capability flag — and
channels treat unknown as "don't downgrade".

The upgrade is guarded by a column-existence check: some databases received
this column via a manual `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` hotfix
before this migration shipped, and the guard lets those converge cleanly.

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4g5h6
Create Date: 2026-07-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: str | Sequence[str] | None = 'c1d2e3f4g5h6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c['name'] == 'supports_animation'
               for c in inspector.get_columns('display_clients'))


def upgrade() -> None:
    if _column_exists():
        return
    op.add_column('display_clients',
                  sa.Column('supports_animation', sa.Boolean(), nullable=True))


def downgrade() -> None:
    if _column_exists():
        op.drop_column('display_clients', 'supports_animation')
