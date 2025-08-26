"""
Channel-related schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.common import TimestampMixin


class ChannelStatusModel(BaseModel):
    """Channel status information"""
    last_update: Optional[str] = Field(None, alias="lastUpdate")
    last_error: Optional[str] = Field(None, alias="lastError")
    using_fallback: Optional[bool] = Field(False, alias="usingFallback")
    
    class Config:
        populate_by_name = True


class ChannelBase(BaseModel):
    """Base channel schema"""
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    license: Optional[str] = None
    repo_url: Optional[str] = Field(None, alias="repoUrl")
    
    class Config:
        populate_by_name = True


class ChannelCreate(ChannelBase):
    """Schema for creating channels"""
    id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    manifest: Optional[Dict[str, Any]] = None


class ChannelUpdate(BaseModel):
    """Schema for updating channels"""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    repo_url: Optional[str] = Field(None, alias="repoUrl")
    config: Optional[Dict[str, Any]] = None
    manifest: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class ChannelResponse(ChannelBase, TimestampMixin):
    """Schema for channel responses"""
    id: str
    schema_version: Optional[str] = Field("2.1", alias="schemaVersion")
    rel_logo_image_path: Optional[str] = Field(None, alias="relLogoImagePath")
    settings_type: str = Field("simple", alias="settingsType")
    status: Optional[ChannelStatusModel] = None
    permissions: Optional[List[str]] = []
    has_ui: Optional[bool] = Field(False, alias="hasUI")
    has_assets: Optional[bool] = Field(False, alias="hasAssets")
    channel_dir: Optional[str] = Field(None, alias="channelDir")
    config: Optional[Dict[str, Any]] = None
    manifest: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True


class ChannelConfigResponse(BaseModel):
    """Channel configuration response"""
    name: str
    description: str
    settings_type: str = Field(alias="settingsType")
    settings: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class ChannelHealthResponse(BaseModel):
    """Channel health check response"""
    status: str  # "healthy", "warning", "error"
    last_check: datetime
    last_update: Optional[datetime] = None
    last_error: Optional[str] = None
    using_fallback: bool = False
    response_time_ms: Optional[float] = None


class ChannelTokenResponse(BaseModel):
    """Channel authentication token response"""
    token: str
    expires_at: Optional[datetime] = None
    permissions: List[str] = []


class ImageRequestBody(BaseModel):
    """Image request parameters"""
    resolution: Optional[List[int]] = None
    format: Optional[str] = "jpeg"
    quality: Optional[int] = 85
    force_refresh: Optional[bool] = Field(False, alias="forceRefresh")
    
    class Config:
        populate_by_name = True


class ChannelTestRequest(BaseModel):
    """Channel test request parameters"""
    test_type: Optional[str] = "basic"
    parameters: Optional[Dict[str, Any]] = None


class ChannelTestResponse(BaseModel):
    """Channel test result"""
    success: bool
    test_type: str
    duration_ms: float
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SubchannelInfo(BaseModel):
    """Subchannel information"""
    id: str
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class SubchannelConfig(BaseModel):
    """Subchannel configuration"""
    subchannels: List[SubchannelInfo]
    default_subchannel: Optional[str] = None
    selection_mode: str = "manual"  # "manual", "auto", "rotation"


class ChannelManifest(BaseModel):
    """Channel manifest information"""
    channels: List[ChannelResponse]
    total: int
    last_updated: datetime
    schema_version: str = "2.1"
