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

class ClearSceneCommand(BaseModel):
    type: str = "clear_scene"
    assignment_id: str
    timestamp: datetime
