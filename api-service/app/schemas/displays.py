"""
Display client related schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.common import TimestampMixin, PaginatedResponse


class DisplayCapabilities(BaseModel):
    """Display client capabilities"""
    resolution: List[int]
    supported_formats: List[str] = Field(alias="supportedFormats")
    orientation: Optional[str] = None
    refresh_rate_hz: Optional[float] = Field(None, alias="refreshRateHz")
    redis_distribution: bool = Field(False, alias="redisDistribution")
    content_claiming: bool = Field(False, alias="contentClaiming")
    
    class Config:
        populate_by_name = True


class DisplayClientBase(BaseModel):
    """Base display client schema"""
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    hostname: Optional[str] = None
    webhook_port: Optional[int] = Field(None, alias="webhookPort")
    client_version: Optional[str] = Field(None, alias="clientVersion")
    tags: Optional[List[str]] = None
    
    class Config:
        populate_by_name = True


class DisplayClientRegistration(DisplayClientBase):
    """Schema for display client registration"""
    capabilities: DisplayCapabilities


class DisplayClientUpdate(BaseModel):
    """Schema for updating display clients"""
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    hostname: Optional[str] = None
    webhook_port: Optional[int] = Field(None, alias="webhookPort")
    client_version: Optional[str] = Field(None, alias="clientVersion")
    tags: Optional[List[str]] = None
    
    class Config:
        populate_by_name = True


class DisplayClientResponse(DisplayClientBase, TimestampMixin):
    """Schema for display client responses"""
    id: str
    device_type: Optional[str] = Field(None, alias="deviceType")
    display_type: Optional[str] = Field(None, alias="displayType")
    discovery_method: Optional[str] = Field(None, alias="discoveryMethod")
    auto_discovered: Optional[bool] = Field(None, alias="autoDiscovered")
    width: Optional[int] = None
    height: Optional[int] = None
    orientation: Optional[str] = None
    redis_distribution: Optional[bool] = Field(None, alias="redisDistribution")
    content_claiming: Optional[bool] = Field(None, alias="contentClaiming")
    is_online: Optional[bool] = Field(None, alias="isOnline")
    last_seen: Optional[datetime] = Field(None, alias="lastSeen")
    assigned_scene_id: Optional[str] = Field(None, alias="assignedSceneId")
    current_content_hash: Optional[str] = Field(None, alias="currentContentHash")
    websocket_connection_id: Optional[str] = Field(None, alias="websocketConnectionId")
    
    class Config:
        from_attributes = True
        populate_by_name = True


class DisplayClientListResponse(PaginatedResponse):
    """Paginated display client list response"""
    data: List[DisplayClientResponse]


class DisplayStatusResponse(BaseModel):
    """Display status response"""
    id: str
    display_client_id: str = Field(alias="displayClientId")
    current_scene: Optional[str] = Field(None, alias="currentScene")
    content_hash: Optional[str] = Field(None, alias="contentHash")
    last_content_update: Optional[datetime] = Field(None, alias="lastContentUpdate")
    battery_level: Optional[float] = Field(None, alias="batteryLevel")
    signal_strength: Optional[int] = Field(None, alias="signalStrength")
    temperature: Optional[float] = None
    
    class Config:
        populate_by_name = True


class SceneAssignment(BaseModel):
    """Scene assignment request"""
    scene_id: str = Field(alias="sceneId")
    
    class Config:
        populate_by_name = True


class ContentClaimRequest(BaseModel):
    """Content claim request"""
    scene_id: str = Field(alias="sceneId")
    content_id: str = Field(alias="contentId")
    assignment_id: Optional[str] = Field(None, alias="assignmentId")
    
    class Config:
        populate_by_name = True


class ContentClaimResponse(BaseModel):
    """Content claim response"""
    lease_id: str = Field(alias="leaseId")
    content_id: str = Field(alias="contentId")
    expires_at: datetime = Field(alias="expiresAt")
    assignment_id: Optional[str] = Field(None, alias="assignmentId")
    
    class Config:
        populate_by_name = True


class AcknowledgmentRequest(BaseModel):
    """Content acknowledgment request"""
    lease_id: str = Field(alias="leaseId")
    content_id: Optional[str] = Field(None, alias="contentId")
    status: Optional[str] = "acknowledged"
    
    class Config:
        populate_by_name = True


class DisplayHardware(BaseModel):
    """Display hardware information"""
    type: str
    resolution: List[int]
    available: bool
    orientation: Optional[str] = None
    
    
class DisplayImage(BaseModel):
    """Display image information"""
    url: str
    width: int
    height: int
    format: str
    size_bytes: Optional[int] = Field(None, alias="sizeBytes")
    
    class Config:
        populate_by_name = True


class LegacyDisplayStatusResponse(BaseModel):
    """Legacy display status response for backward compatibility"""
    hardware: DisplayHardware
    current_scene: Optional[str] = Field(None, alias="currentScene")
    current_image: Optional[DisplayImage] = Field(None, alias="currentImage")
    resolution: List[int]
    
    class Config:
        populate_by_name = True
