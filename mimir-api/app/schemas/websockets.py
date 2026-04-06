"""
WebSocket and real-time communication schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class WebSocketEvent(BaseModel):
    """Base WebSocket event schema"""
    event: str
    data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    sequence_id: Optional[int] = Field(None, alias="sequenceId")
    
    class Config:
        populate_by_name = True


class WebSocketMessage(BaseModel):
    """WebSocket message wrapper"""
    type: str = "message"
    payload: WebSocketEvent
    connection_id: Optional[str] = None


class HeartbeatEvent(BaseModel):
    """WebSocket heartbeat event"""
    event: str = "ping"
    data: Dict[str, str] = Field(default_factory=lambda: {"timestamp": datetime.now().isoformat()})
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class StateSync(BaseModel):
    """State synchronization request/response"""
    event: str = "state_sync"
    data: Dict[str, Any]
    full_state: bool = True
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SubscriptionRequest(BaseModel):
    """WebSocket subscription request"""
    event: str = "subscribe"
    data: Dict[str, List[str]]  # {"events": ["scene_changed", "display_status"]}
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SubscriptionResponse(BaseModel):
    """WebSocket subscription confirmation"""
    event: str = "subscription_confirmed"
    data: Dict[str, List[str]]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class DisplayStatusUpdate(BaseModel):
    """Display status update event"""
    event: str = "display_status_update"
    data: Dict[str, Any]
    display_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SceneChangeRequest(BaseModel):
    """Scene change request event"""
    event: str = "scene_change_request"
    data: Dict[str, str]  # {"scene_id": "...", "display_id": "..."}
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ContentRenderedEvent(BaseModel):
    """Content rendered confirmation event"""
    event: str = "content_rendered"
    data: Dict[str, Any]
    display_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class DisplayErrorEvent(BaseModel):
    """Display error event"""
    event: str = "display_error"
    data: Dict[str, Any]
    display_id: str
    error_type: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class BroadcastEventData(BaseModel):
    """Enhanced broadcast event data"""
    triggered_by: Dict[str, str] = Field(alias="triggeredBy")
    previous_state: Optional[Dict[str, Any]] = Field(None, alias="previousState")
    
    class Config:
        populate_by_name = True


class ConnectionStats(BaseModel):
    """WebSocket connection statistics"""
    total_connections: int
    general_connections: int
    display_connections: int
    connected_displays: List[str]
    uptime_seconds: Optional[float] = None


class WebSocketError(BaseModel):
    """WebSocket error response"""
    event: str = "error"
    data: Dict[str, str]
    error_code: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
