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
Channel-related schemas
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import TimestampMixin


class ChannelStatusModel(BaseModel):
    """Channel status information"""
    last_update: str | None = Field(None, alias="lastUpdate")
    last_error: str | None = Field(None, alias="lastError")
    using_fallback: bool | None = Field(False, alias="usingFallback")

    class Config:
        populate_by_name = True


class ChannelBase(BaseModel):
    """Base channel schema"""
    name: str
    description: str | None = None
    version: str = "1.0.0"
    author: str | None = None
    license: str | None = None
    repo_url: str | None = Field(None, alias="repoUrl")

    class Config:
        populate_by_name = True


class ChannelCreate(ChannelBase):
    """Schema for creating channels"""
    id: str | None = None
    config: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None


class ChannelUpdate(BaseModel):
    """Schema for updating channels"""
    name: str | None = None
    description: str | None = None
    version: str | None = None
    author: str | None = None
    license: str | None = None
    repo_url: str | None = Field(None, alias="repoUrl")
    config: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class ChannelResponse(ChannelBase, TimestampMixin):
    """Schema for channel responses"""
    id: str
    schema_version: str | None = Field("2.1", alias="schemaVersion")
    rel_logo_image_path: str | None = Field(None, alias="relLogoImagePath")
    settings_type: str = Field("simple", alias="settingsType")
    status: ChannelStatusModel | None = None
    permissions: list[str] | None = []
    has_ui: bool | None = Field(False, alias="hasUI")
    has_assets: bool | None = Field(False, alias="hasAssets")
    channel_dir: str | None = Field(None, alias="channelDir")
    config: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None

    class Config:
        from_attributes = True
        populate_by_name = True


class ChannelConfigResponse(BaseModel):
    """Channel configuration response"""
    name: str
    description: str
    settings_type: str = Field(alias="settingsType")
    settings: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class ChannelHealthResponse(BaseModel):
    """Channel health check response"""
    status: str  # "healthy", "warning", "error"
    last_check: datetime
    last_update: datetime | None = None
    last_error: str | None = None
    using_fallback: bool = False
    response_time_ms: float | None = None


class ChannelTokenResponse(BaseModel):
    """Channel authentication token response"""
    token: str
    expires_at: datetime | None = None
    permissions: list[str] = []


class ImageRequestBody(BaseModel):
    """Image request parameters"""
    resolution: list[int] | None = None
    format: str | None = "jpeg"
    quality: int | None = 85
    force_refresh: bool | None = Field(False, alias="forceRefresh")

    class Config:
        populate_by_name = True


class ChannelTestRequest(BaseModel):
    """Channel test request parameters"""
    test_type: str | None = "basic"
    parameters: dict[str, Any] | None = None


class ChannelTestResponse(BaseModel):
    """Channel test result"""
    success: bool
    test_type: str
    duration_ms: float
    message: str | None = None
    details: dict[str, Any] | None = None


class SubchannelInfo(BaseModel):
    """Subchannel information"""
    id: str
    name: str
    description: str | None = None
    type: str | None = None
    config: dict[str, Any] | None = None


class SubchannelConfig(BaseModel):
    """Subchannel configuration"""
    subchannels: list[SubchannelInfo]
    default_subchannel: str | None = None
    selection_mode: str = "manual"  # "manual", "auto", "rotation"


class ChannelManifest(BaseModel):
    """Channel manifest information"""
    channels: list[ChannelResponse]
    total: int
    last_updated: datetime
    schema_version: str = "2.1"
