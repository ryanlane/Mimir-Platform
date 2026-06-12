"""
Scene-related schemas
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import TimestampMixin


class SceneOverlay(BaseModel):
    """Scene overlay configuration"""
    overlays: list[str]
    position: list[str]
    background: bool
    background_color: dict[str, int] = Field(alias="backgroundColor")

    class Config:
        populate_by_name = True


class SceneSchedule(BaseModel):
    """Scene schedule configuration"""
    days: list[str]
    start: str
    end: str
    timezone: str | None = None


class ChannelAssignment(BaseModel):
    """Channel assignment within a scene"""
    channel_id: str
    subchannel_id: str | None = None
    position: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class SceneBase(BaseModel):
    """Base scene schema"""
    name: str
    channels: list[ChannelAssignment]
    overlays: list[str] | None = None
    timing_config: dict[str, Any] | None = Field(None, alias="timingConfig")
    distribution_mode: str | None = Field("push", alias="distributionMode")
    is_active: bool | None = Field(False, alias="isActive")
    update_strategy: str | None = Field("scheduler", alias="updateStrategy", description="scheduler or push")
    push_fallback_poll_seconds: int | None = Field(None, alias="pushFallbackPollSeconds", ge=5, le=7200)

    class Config:
        populate_by_name = True


class SceneCreate(SceneBase):
    """Schema for creating scenes"""
    id: str | None = None
    overlay: SceneOverlay | None = None
    schedule: SceneSchedule | None = None


class SceneUpdate(BaseModel):
    """Schema for updating scenes"""
    name: str | None = None
    channels: list[ChannelAssignment] | None = None
    overlays: list[str] | None = None
    timing_config: dict[str, Any] | None = Field(None, alias="timingConfig")
    distribution_mode: str | None = Field(None, alias="distributionMode")
    is_active: bool | None = Field(None, alias="isActive")
    overlay: SceneOverlay | None = None
    schedule: SceneSchedule | None = None
    update_strategy: str | None = Field(None, alias="updateStrategy")
    push_fallback_poll_seconds: int | None = Field(None, alias="pushFallbackPollSeconds", ge=5, le=7200)

    class Config:
        populate_by_name = True


class SceneResponse(SceneBase, TimestampMixin):
    """Schema for scene responses"""
    id: str
    content_hash: str | None = Field(None, alias="contentHash")
    content_epoch: int | None = Field(None, alias="contentEpoch")
    overlay: SceneOverlay | None = None
    schedule: SceneSchedule | None = None
    # Auto-refresh scheduler summary (derived from SchedulerJob + assignment)
    refresh_schedule: dict[str, Any] | None = Field(
        None,
        alias="refreshSchedule",
        description=(
            "Derived scheduler frequency for this scene: {job_id, freq_unit, freq_value, enabled}. "
            "Provided when a scheduler job assigns this scene; picks the enabled job with the smallest interval."
        ),
        examples=[
            {"job_id": "job-123", "freq_unit": "minute", "freq_value": 5, "enabled": True}
        ],
    )

    class Config:
        from_attributes = True
        populate_by_name = True


class SceneCreateRequest(BaseModel):
    """Legacy scene creation request for backward compatibility"""
    name: str
    channels: list[ChannelAssignment]
    overlay: SceneOverlay | None = None
    schedule: SceneSchedule | None = None
    image_fit: str | None = Field("cover", alias="imageFit")
    theme: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class SceneActivationRequest(BaseModel):
    """Scene activation request"""
    scene_id: str
    display_ids: list[str] | None = None
    force: bool | None = False


class SceneActivationResponse(BaseModel):
    """Scene activation response"""
    scene_id: str
    activated_displays: list[str]
    failed_displays: list[str]
    message: str


class SceneStatusResponse(BaseModel):
    """Scene status information"""
    id: str
    name: str
    is_active: bool
    content_hash: str | None = None
    content_epoch: int | None = None
    assigned_displays: list[str]
    last_updated: datetime | None = None
    distribution_status: dict[str, Any] | None = None


class SceneListResponse(BaseModel):
    """Response for listing scenes"""
    scenes: list[SceneResponse]
    total: int
    limit: int
    offset: int


class SceneActivation(BaseModel):
    """Scene activation configuration"""
    scene_id: str
    display_ids: list[str] | None = None
    force: bool | None = False


class ScheduleConfig(BaseModel):
    """Legacy schedule configuration for backward compatibility"""
    days: list[str]
    start: str
    end: str
    timezone: str | None = None
