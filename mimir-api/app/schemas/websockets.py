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
WebSocket and real-time communication schemas
"""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class WebSocketEvent(BaseModel):
    """Base WebSocket event schema"""
    event: str
    data: dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sequence_id: int | None = Field(None, alias="sequenceId")

    class Config:
        populate_by_name = True


class WebSocketMessage(BaseModel):
    """WebSocket message wrapper"""
    type: str = "message"
    payload: WebSocketEvent
    connection_id: str | None = None


class HeartbeatEvent(BaseModel):
    """WebSocket heartbeat event"""
    event: str = "ping"
    data: dict[str, str] = Field(default_factory=lambda: {"timestamp": datetime.now(timezone.utc).isoformat()})
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StateSync(BaseModel):
    """State synchronization request/response"""
    event: str = "state_sync"
    data: dict[str, Any]
    full_state: bool = True
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SubscriptionRequest(BaseModel):
    """WebSocket subscription request"""
    event: str = "subscribe"
    data: dict[str, list[str]]  # {"events": ["scene_changed", "display_status"]}
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SubscriptionResponse(BaseModel):
    """WebSocket subscription confirmation"""
    event: str = "subscription_confirmed"
    data: dict[str, list[str]]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DisplayStatusUpdate(BaseModel):
    """Display status update event"""
    event: str = "display_status_update"
    data: dict[str, Any]
    display_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SceneChangeRequest(BaseModel):
    """Scene change request event"""
    event: str = "scene_change_request"
    data: dict[str, str]  # {"scene_id": "...", "display_id": "..."}
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContentRenderedEvent(BaseModel):
    """Content rendered confirmation event"""
    event: str = "content_rendered"
    data: dict[str, Any]
    display_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DisplayErrorEvent(BaseModel):
    """Display error event"""
    event: str = "display_error"
    data: dict[str, Any]
    display_id: str
    error_type: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BroadcastEventData(BaseModel):
    """Enhanced broadcast event data"""
    triggered_by: dict[str, str] = Field(alias="triggeredBy")
    previous_state: dict[str, Any] | None = Field(None, alias="previousState")

    class Config:
        populate_by_name = True


class ConnectionStats(BaseModel):
    """WebSocket connection statistics"""
    total_connections: int
    general_connections: int
    display_connections: int
    connected_displays: list[str]
    uptime_seconds: float | None = None


class WebSocketError(BaseModel):
    """WebSocket error response"""
    event: str = "error"
    data: dict[str, str]
    error_code: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
