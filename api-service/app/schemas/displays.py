"""
Display client related schemas
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.common import TimestampMixin


class DisplayCapabilities(BaseModel):
    """Display client capabilities"""
    resolution: List[int]
    supported_formats: List[str]
    orientation: Optional[str] = None
    refresh_rate_hz: Optional[float] = None
    redis_distribution: bool = False
    content_claiming: bool = False


class DisplayClientBase(BaseModel):
    """Base display client schema"""
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    hostname: Optional[str] = None
    webhook_port: Optional[int] = None
    client_version: Optional[str] = None
    tags: Optional[List[str]] = None


class DisplayClientRegistration(DisplayClientBase):
    """Schema for display client registration"""
    capabilities: DisplayCapabilities


class DisplayClientUpdate(BaseModel):
    """Schema for updating display clients"""
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    hostname: Optional[str] = None
    webhook_port: Optional[int] = None
    client_version: Optional[str] = None
    tags: Optional[List[str]] = None


class DisplayClientResponse(DisplayClientBase, TimestampMixin):
    """Schema for display client responses"""
    id: str
    device_type: Optional[str] = None
    display_type: Optional[str] = None
    discovery_method: Optional[str] = None
    auto_discovered: Optional[bool] = None
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: Optional[str] = None
    redis_distribution: Optional[bool] = None
    content_claiming: Optional[bool] = None
    is_online: Optional[bool] = None
    last_seen: Optional[datetime] = None
    assigned_scene_id: Optional[str] = None
    current_content_hash: Optional[str] = None
    websocket_connection_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class DisplayStatusResponse(BaseModel):
    """Display status response"""
    id: str
    display_client_id: str
    current_scene: Optional[str] = None
    content_hash: Optional[str] = None
    last_content_update: Optional[datetime] = None
    battery_level: Optional[float] = None
    signal_strength: Optional[int] = None
    temperature: Optional[float] = None


class SceneAssignment(BaseModel):
    """Scene assignment request"""
    scene_id: str


class ContentClaimRequest(BaseModel):
    """Content claim request"""
    scene_id: str
    content_id: str
    assignment_id: Optional[str] = None


class ContentClaimResponse(BaseModel):
    """Content claim response"""
    lease_id: str
    content_id: str
    expires_at: datetime
    assignment_id: Optional[str] = None
