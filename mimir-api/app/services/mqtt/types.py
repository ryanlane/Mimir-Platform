# app/services/mqtt/types.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime

class StatusPayload(BaseModel):
    status: str
    timestamp: datetime
    reason: Optional[str] = None
    version: Optional[str] = None

class AssignDelivery(BaseModel):
    type: str = "url"
    url: HttpUrl
    content_type: str = "image/png"
    etag: str = "v1"
    ttl_seconds: int = 3600

class AssignContent(BaseModel):
    delivery: AssignDelivery
    metadata: Dict[str, Any] = {}

class AssignCommand(BaseModel):
    type: str = "assign"
    assignment_id: str
    sequence: int = 1
    scene_id: str
    scene_name: str
    content: AssignContent
    timestamp: datetime
    # Update semantics:
    # update_type: "push" for real-time push updates, "scheduled" for polling/scheduler-driven.
    # refresh_interval_s: Polling interval in seconds when update_type == "scheduled".
    #   Must be omitted or null when update_type == "push".
    update_type: Optional[str] = None
    refresh_interval_s: Optional[int] = None

    class Config:
        json_schema_extra = {
            "description": (
                "Assign command sent to display clients. New optional fields 'update_type' and "
                "'refresh_interval_s' communicate whether the scene should be updated by push "
                "events or by client polling. Older clients can ignore these fields safely."
            )
        }

class ClearSceneCommand(BaseModel):
    type: str = "clear_scene"
    assignment_id: str
    timestamp: datetime
