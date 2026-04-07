"""
Display client related schemas
"""
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.common import TimestampMixin, PaginatedResponse


class DisplayCapabilities(BaseModel):
    """Display client capabilities"""
    resolution: list[int]
    supported_formats: list[str] = Field(alias="supportedFormats")
    orientation: str | None = None
    refresh_rate_hz: float | None = Field(None, alias="refreshRateHz")
    redis_distribution: bool = Field(False, alias="redisDistribution")
    content_claiming: bool = Field(False, alias="contentClaiming")
    
    class Config:
        populate_by_name = True


class AssignedScene(BaseModel):
    """Assigned scene information with optional subchannel"""
    id: str = Field(description="Scene ID")
    subchannel_id: str | None = Field(None, alias="subchannelId", description="Optional subchannel ID")
    
    class Config:
        populate_by_name = True


class DisplayClientBase(BaseModel):
    """Base display client schema"""
    name: str
    location: str | None = None
    description: str | None = None
    hostname: str | None = None
    webhook_port: int | None = Field(None, alias="webhookPort")
    client_version: str | None = Field(None, alias="clientVersion")
    tags: list[str] | None = None
    
    class Config:
        populate_by_name = True


class DisplayClientRegistration(DisplayClientBase):
    """Schema for display client registration"""
    capabilities: DisplayCapabilities


class DisplayClientUpdate(BaseModel):
    """Schema for updating display clients"""
    name: str | None = None
    location: str | None = None
    description: str | None = None
    hostname: str | None = None
    webhook_port: int | None = Field(None, alias="webhookPort")
    client_version: str | None = Field(None, alias="clientVersion")
    tags: list[str] | None = None
    
    class Config:
        populate_by_name = True


class DisplayClientResponse(DisplayClientBase, TimestampMixin):
    """Schema for display client responses"""
    id: str
    device_type: str | None = Field(None, alias="deviceType")
    display_type: str | None = Field(None, alias="displayType")
    discovery_method: str | None = Field(None, alias="discoveryMethod")
    auto_discovered: bool | None = Field(None, alias="autoDiscovered")
    # Networking
    ip_address: str | None = Field(None, alias="ipAddress", description="Primary IP address if known")
    ip_addresses: list[str] | None = Field(None, alias="ipAddresses", description="All known IP addresses")
    width: int | None = None
    height: int | None = None
    orientation: str | None = None
    supported_formats: list[str] | None = Field(None, alias="supportedFormats", description="List of supported image format strings (e.g. ['jpg','bmp1'])")
    redis_distribution: bool | None = Field(None, alias="redisDistribution")
    content_claiming: bool | None = Field(None, alias="contentClaiming")
    is_online: bool | None = Field(None, alias="isOnline")
    last_seen: datetime | None = Field(None, alias="lastSeen")
    assigned_scene_id: AssignedScene | None = Field(None, alias="assignedSceneId")
    current_content_hash: str | None = Field(None, alias="currentContentHash")
    websocket_connection_id: str | None = Field(None, alias="websocketConnectionId")
    
    class Config:
        from_attributes = True
        populate_by_name = True


class DisplayClientListResponse(PaginatedResponse):
    """Paginated display client list response"""
    data: list[DisplayClientResponse]


class DisplayStatusResponse(BaseModel):
    """Display status response"""
    id: str
    display_client_id: str = Field(alias="displayClientId")
    current_scene: str | None = Field(None, alias="currentScene")
    content_hash: str | None = Field(None, alias="contentHash")
    last_content_update: datetime | None = Field(None, alias="lastContentUpdate")
    battery_level: float | None = Field(None, alias="batteryLevel")
    signal_strength: int | None = Field(None, alias="signalStrength")
    temperature: float | None = None
    
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
    assignment_id: str | None = Field(None, alias="assignmentId")
    
    class Config:
        populate_by_name = True


class ContentClaimResponse(BaseModel):
    """Content claim response"""
    lease_id: str = Field(alias="leaseId")
    content_id: str = Field(alias="contentId")
    expires_at: datetime = Field(alias="expiresAt")
    assignment_id: str | None = Field(None, alias="assignmentId")
    
    class Config:
        populate_by_name = True


class AcknowledgmentRequest(BaseModel):
    """Content acknowledgment request"""
    lease_id: str = Field(alias="leaseId")
    content_id: str | None = Field(None, alias="contentId")
    status: str | None = "acknowledged"
    
    class Config:
        populate_by_name = True


class DisplayHardware(BaseModel):
    """Display hardware information"""
    type: str
    resolution: list[int]
    available: bool
    orientation: str | None = None
    
    
class DisplayImage(BaseModel):
    """Display image information"""
    url: str
    width: int
    height: int
    format: str
    size_bytes: int | None = Field(None, alias="sizeBytes")
    
    class Config:
        populate_by_name = True


class PairClaimRequest(BaseModel):
    """Submit a 6-character pairing code to claim a display."""
    code: str = Field(description="6-character pairing code shown on the display")
    name: str | None = Field(None, description="Optional friendly name for the display")
    location: str | None = Field(None, description="Optional physical location")


class PairStatusResponse(BaseModel):
    """Status of a pending pairing code."""
    code: str
    status: str  # "pending" | "not_found"
    device_id: str | None = None
    expires_in: int | None = Field(None, alias="expiresIn", description="Approximate TTL in seconds")

    class Config:
        populate_by_name = True


class LegacyDisplayStatusResponse(BaseModel):
    """Legacy display status response for backward compatibility"""
    hardware: DisplayHardware
    current_scene: str | None = Field(None, alias="currentScene")
    current_image: DisplayImage | None = Field(None, alias="currentImage")
    resolution: list[int]
    
    class Config:
        populate_by_name = True
