"""
Overlay-related schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from app.schemas.common import TimestampMixin


class OverlayBase(BaseModel):
    """Base overlay schema"""
    name: str
    overlay_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class OverlayCreate(OverlayBase):
    """Schema for creating overlays"""
    id: Optional[str] = None


class OverlayUpdate(BaseModel):
    """Schema for updating overlays"""
    name: Optional[str] = None
    overlay_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class OverlayResponse(OverlayBase, TimestampMixin):
    """Schema for overlay responses"""
    id: str
    
    class Config:
        from_attributes = True
