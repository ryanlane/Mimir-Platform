"""
Overlay-related schemas
"""
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import TimestampMixin


class OverlayBase(BaseModel):
    """Base overlay schema"""
    name: str
    overlay_type: str | None = Field(None, alias="overlayType")
    config: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class OverlayCreate(OverlayBase):
    """Schema for creating overlays"""
    id: str | None = None


class OverlayUpdate(BaseModel):
    """Schema for updating overlays"""
    name: str | None = None
    overlay_type: str | None = Field(None, alias="overlayType")
    config: dict[str, Any] | None = None

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
    description: str | None = None
    channel: str | None = None
    path_root: str | None = Field(None, alias="pathRoot")

    class Config:
        populate_by_name = True


class OverlayListResponse(BaseModel):
    """Response for listing overlays"""
    overlays: list[OverlayResponse]
    total: int
    limit: int
    offset: int
