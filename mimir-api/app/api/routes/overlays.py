"""
Overlay API Routes
FastAPI router for overlay-related endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import Overlay
from app.schemas.overlays import (
    OverlayCreate,
    OverlayListResponse,
    OverlayResponse,
    OverlayUpdate,
)

router = APIRouter(prefix="/overlays", tags=["overlays"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=OverlayListResponse)
async def list_overlays(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get paginated list of overlays"""
    total = db.query(Overlay).count()
    overlays = db.query(Overlay).offset(offset).limit(limit).all()

    overlay_responses = [
        OverlayResponse.model_validate(overlay) for overlay in overlays
    ]

    return OverlayListResponse(
        overlays=overlay_responses,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{overlay_id}", response_model=OverlayResponse)
async def get_overlay(
    overlay_id: str,
    db: Session = Depends(get_db)
):
    """Get overlay by ID"""
    overlay = db.query(Overlay).filter(Overlay.id == overlay_id).first()
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")

    return OverlayResponse.model_validate(overlay)


@router.post("", response_model=OverlayResponse)
async def create_overlay(
    overlay_data: OverlayCreate,
    db: Session = Depends(get_db)
):
    """Create a new overlay"""
    overlay = Overlay(
        id=overlay_data.id,
        name=overlay_data.name,
        overlay_type=overlay_data.overlay_type,
        config=overlay_data.config
    )

    db.add(overlay)
    db.commit()
    db.refresh(overlay)

    return OverlayResponse.model_validate(overlay)


@router.put("/{overlay_id}", response_model=OverlayResponse)
async def update_overlay(
    overlay_id: str,
    overlay_data: OverlayUpdate,
    db: Session = Depends(get_db)
):
    """Update overlay by ID"""
    overlay = db.query(Overlay).filter(Overlay.id == overlay_id).first()
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")

    # Update only provided fields
    update_data = overlay_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(overlay, key, value)

    db.commit()
    db.refresh(overlay)

    return OverlayResponse.model_validate(overlay)


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
