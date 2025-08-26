"""
Overlay API Routes
FastAPI router for overlay-related endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.base import SessionLocal
from app.db.models import Overlay
from app.schemas.overlays import OverlayResponse
from app.schemas.common import PaginationMeta


router = APIRouter(prefix="/overlays", tags=["overlays"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=dict)
async def list_overlays(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get paginated list of overlays"""
    total = db.query(Overlay).count()
    overlays = db.query(Overlay).offset(offset).limit(limit).all()
    
    result = [
        OverlayResponse(
            id=overlay.id,
            name=overlay.name,
            overlay_type=overlay.overlay_type,
            config=overlay.config,
            created_at=overlay.created_at,
            updated_at=overlay.updated_at
        ) for overlay in overlays
    ]
    
    return {
        "overlays": result,
        "meta": PaginationMeta(total=total, limit=limit, offset=offset)
    }


@router.get("/{overlay_id}", response_model=OverlayResponse)
async def get_overlay(
    overlay_id: str,
    db: Session = Depends(get_db)
):
    """Get overlay by ID"""
    overlay = db.query(Overlay).filter(Overlay.id == overlay_id).first()
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    return OverlayResponse(
        id=overlay.id,
        name=overlay.name,
        overlay_type=overlay.overlay_type,
        config=overlay.config,
        created_at=overlay.created_at,
        updated_at=overlay.updated_at
    )


@router.post("", response_model=OverlayResponse)
async def create_overlay(
    overlay_data: dict,
    db: Session = Depends(get_db)
):
    """Create a new overlay"""
    overlay = Overlay(
        id=overlay_data.get("id"),
        name=overlay_data["name"],
        overlay_type=overlay_data.get("overlay_type"),
        config=overlay_data.get("config", {})
    )
    
    db.add(overlay)
    db.commit()
    db.refresh(overlay)
    
    return OverlayResponse(
        id=overlay.id,
        name=overlay.name,
        overlay_type=overlay.overlay_type,
        config=overlay.config,
        created_at=overlay.created_at,
        updated_at=overlay.updated_at
    )


@router.put("/{overlay_id}", response_model=OverlayResponse)
async def update_overlay(
    overlay_id: str,
    overlay_data: dict,
    db: Session = Depends(get_db)
):
    """Update overlay by ID"""
    overlay = db.query(Overlay).filter(Overlay.id == overlay_id).first()
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    for key, value in overlay_data.items():
        if hasattr(overlay, key):
            setattr(overlay, key, value)
    
    db.commit()
    db.refresh(overlay)
    
    return OverlayResponse(
        id=overlay.id,
        name=overlay.name,
        overlay_type=overlay.overlay_type,
        config=overlay.config,
        created_at=overlay.created_at,
        updated_at=overlay.updated_at
    )


@router.delete("/{overlay_id}")
async def delete_overlay(
    overlay_id: str,
    db: Session = Depends(get_db)
):
    """Delete overlay by ID"""
    overlay = db.query(Overlay).filter(Overlay.id == overlay_id).first()
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    db.delete(overlay)
    db.commit()
    
    return {"message": "Overlay deleted successfully"}
