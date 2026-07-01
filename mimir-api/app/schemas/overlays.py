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

"""
Overlay-related schemas
"""
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import TimestampMixin


class OverlayBase(BaseModel):
    """Base overlay schema"""
    name: str
    description: str | None = None
    channel: Any | None = None
    path_root: str | None = Field(None, alias="pathRoot")

    class Config:
        populate_by_name = True


class OverlayCreate(OverlayBase):
    """Schema for creating overlays"""
    id: str | None = None


class OverlayUpdate(BaseModel):
    """Schema for updating overlays"""
    name: str | None = None
    description: str | None = None
    channel: Any | None = None
    path_root: str | None = Field(None, alias="pathRoot")

    class Config:
        populate_by_name = True


class OverlayResponse(OverlayBase, TimestampMixin):
    """Schema for overlay responses"""
    id: str

    class Config:
        from_attributes = True
        populate_by_name = True


class OverlayListResponse(BaseModel):
    """Response for listing overlays"""
    overlays: list[OverlayResponse]
    total: int
    limit: int
    offset: int
