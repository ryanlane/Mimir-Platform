"""
Overlay-related schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.schemas.common import TimestampMixin


class OverlayBase(BaseModel):
    """Base overlay schema"""
    name: str
    overlay_type: Optional[str] = Field(None, alias="overlayType")
    config: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class OverlayCreate(OverlayBase):
    """Schema for creating overlays"""
    id: Optional[str] = None


class OverlayUpdate(BaseModel):
    """Schema for updating overlays"""
    name: Optional[str] = None
    overlay_type: Optional[str] = Field(None, alias="overlayType")
    config: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class OverlayResponse(OverlayBase, TimestampMixin):
    """Schema for overlay responses"""
    id: str
    
    class Config:
        from_attributes = True
        populate_by_name = True


# Legacy response format for backward compatibility
class LegacyOverlayResponse(BaseModel):
    """Legacy overlay response format"""
    id: str
    name: str
    description: Optional[str] = None
    channel: Optional[str] = None
    path_root: Optional[str] = Field(None, alias="pathRoot")
    
    class Config:
        populate_by_name = True


class OverlayListResponse(BaseModel):
    """Response for listing overlays"""
    overlays: List[OverlayResponse]
    total: int
    limit: int
    offset: int
