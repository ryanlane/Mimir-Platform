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

"""merge scheduler tables and content_variant branches

Revision ID: b9c8d7e6f5a4
Revises: 3c8b4f7ffefc, a1b2c3d4e5f6
Create Date: 2026-06-24

"""
from collections.abc import Sequence

revision: str = 'b9c8d7e6f5a4'
down_revision: str | Sequence[str] | None = ('3c8b4f7ffefc', 'a1b2c3d4e5f6')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
