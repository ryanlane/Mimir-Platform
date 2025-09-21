"""
Scene-related schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.common import TimestampMixin


class SceneOverlay(BaseModel):
    """Scene overlay configuration"""
    overlays: List[str]
    position: List[str]
    background: bool
    background_color: Dict[str, int] = Field(alias="backgroundColor")
    
    class Config:
        populate_by_name = True


class SceneSchedule(BaseModel):
    """Scene schedule configuration"""
    days: List[str]
    start: str
    end: str
    timezone: Optional[str] = None


class ChannelAssignment(BaseModel):
    """Channel assignment within a scene"""
    channel_id: str
    subchannel_id: Optional[str] = None
    position: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None


class SceneBase(BaseModel):
    """Base scene schema"""
    name: str
    channels: List[ChannelAssignment]
    overlays: Optional[List[str]] = None
    timing_config: Optional[Dict[str, Any]] = Field(None, alias="timingConfig")
    distribution_mode: Optional[str] = Field("push", alias="distributionMode")
    is_active: Optional[bool] = Field(False, alias="isActive")
    update_strategy: Optional[str] = Field("scheduler", alias="updateStrategy", description="scheduler or push")
    push_fallback_poll_seconds: Optional[int] = Field(None, alias="pushFallbackPollSeconds", ge=5, le=3600)
    
    class Config:
        populate_by_name = True


class SceneCreate(SceneBase):
    """Schema for creating scenes"""
    id: Optional[str] = None
    overlay: Optional[SceneOverlay] = None
    schedule: Optional[SceneSchedule] = None


class SceneUpdate(BaseModel):
    """Schema for updating scenes"""
    name: Optional[str] = None
    channels: Optional[List[ChannelAssignment]] = None
    overlays: Optional[List[str]] = None
    timing_config: Optional[Dict[str, Any]] = Field(None, alias="timingConfig")
    distribution_mode: Optional[str] = Field(None, alias="distributionMode")
    is_active: Optional[bool] = Field(None, alias="isActive")
    overlay: Optional[SceneOverlay] = None
    schedule: Optional[SceneSchedule] = None
    update_strategy: Optional[str] = Field(None, alias="updateStrategy")
    push_fallback_poll_seconds: Optional[int] = Field(None, alias="pushFallbackPollSeconds", ge=5, le=3600)
    
    class Config:
        populate_by_name = True


class SceneResponse(SceneBase, TimestampMixin):
    """Schema for scene responses"""
    id: str
    content_hash: Optional[str] = Field(None, alias="contentHash")
    content_epoch: Optional[int] = Field(None, alias="contentEpoch")
    overlay: Optional[SceneOverlay] = None
    schedule: Optional[SceneSchedule] = None
    
    class Config:
        from_attributes = True
        populate_by_name = True


class SceneCreateRequest(BaseModel):
    """Legacy scene creation request for backward compatibility"""
    name: str
    channels: List[ChannelAssignment]
    overlay: Optional[SceneOverlay] = None
    schedule: Optional[SceneSchedule] = None
    image_fit: Optional[str] = Field("cover", alias="imageFit")
    theme: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class SceneActivationRequest(BaseModel):
    """Scene activation request"""
    scene_id: str
    display_ids: Optional[List[str]] = None
    force: Optional[bool] = False


class SceneActivationResponse(BaseModel):
    """Scene activation response"""
    scene_id: str
    activated_displays: List[str]
    failed_displays: List[str]
    message: str


class SceneStatusResponse(BaseModel):
    """Scene status information"""
    id: str
    name: str
    is_active: bool
    content_hash: Optional[str] = None
    content_epoch: Optional[int] = None
    assigned_displays: List[str]
    last_updated: Optional[datetime] = None
    distribution_status: Optional[Dict[str, Any]] = None


class SceneListResponse(BaseModel):
    """Response for listing scenes"""
    scenes: List[SceneResponse]
    total: int
    limit: int
    offset: int


class SceneActivation(BaseModel):
    """Scene activation configuration"""
    scene_id: str
    display_ids: Optional[List[str]] = None
    force: Optional[bool] = False


class ScheduleConfig(BaseModel):
    """Legacy schedule configuration for backward compatibility"""
    days: List[str]
    start: str
    end: str
    timezone: Optional[str] = None
