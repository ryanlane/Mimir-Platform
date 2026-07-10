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

"""add display_clients web_token column

Web Screens are browser-only displays addressed by a secret URL token: any
device with a browser loads /d/<token> and becomes a display. The token is
the credential — unguessable, revoked by deleting the display.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: str | Sequence[str] | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c['name'] == 'web_token'
               for c in inspector.get_columns('display_clients'))


def upgrade() -> None:
    if _column_exists():
        return
    op.add_column('display_clients', sa.Column('web_token', sa.String(), nullable=True))
    op.create_index('ix_display_clients_web_token', 'display_clients', ['web_token'], unique=True)


def downgrade() -> None:
    if _column_exists():
        op.drop_index('ix_display_clients_web_token', table_name='display_clients')
        op.drop_column('display_clients', 'web_token')
