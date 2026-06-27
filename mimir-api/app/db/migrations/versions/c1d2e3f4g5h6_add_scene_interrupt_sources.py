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

"""add scene interrupt_sources column

Adds the interrupt_sources JSON column to the scenes table. This column holds
an ordered list of now-playing channel sources that can pre-empt the scene's
base content when the channel reports is_playing=true. Existing rows default
to NULL (no interrupt sources configured).

Revision ID: c1d2e3f4g5h6
Revises: b9c8d7e6f5a4
Create Date: 2026-06-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c1d2e3f4g5h6'
down_revision: str | Sequence[str] | None = 'b9c8d7e6f5a4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('scenes', sa.Column('interrupt_sources', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('scenes', 'interrupt_sources')
