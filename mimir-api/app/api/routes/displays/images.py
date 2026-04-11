"""Image and last-image endpoints for displays."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import DisplayClient, DisplaySceneImage
from app.services.display_image_persistence import DisplayImagePersistenceService
from app.services.display_last_image import display_last_image_store
from ._helpers import get_db, _build_thumbnail_url


router = APIRouter()


def _display_lookup_ids(db: Session, display_id: str) -> list[str]:
    lookup_ids: list[str] = []
    for candidate in (display_id,):
        if candidate and candidate not in lookup_ids:
            lookup_ids.append(candidate)

    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if client:
        for candidate in (client.hostname, client.name):
            if candidate and candidate not in lookup_ids:
                lookup_ids.append(candidate)

    return lookup_ids


def _get_persisted_image_record(
    svc: DisplayImagePersistenceService,
    lookup_ids: list[str],
    scene_id: str,
    subchannel_id: str | None,
):
    for candidate in lookup_ids:
        rec = svc.get_last_for_display_scene(candidate, scene_id, subchannel_id)
        if rec:
            return rec
    return None


@router.get("/{device_id}/last-image", response_model=dict)
async def get_last_image(device_id: str):
    """Return the last image command issued to a display (in-memory, best effort)."""
    record = display_last_image_store.get(device_id)
    if not record:
        raise HTTPException(status_code=404, detail="No image record for device")
    return record.to_dict()


@router.get("/{display_id}/scenes/{scene_id}/last-image", response_model=dict)
async def get_persisted_last_image(
    display_id: str,
    scene_id: str,
    subchannel_id: str | None = None,
    db: Session = Depends(get_db)
):
    """Return the persisted last image metadata for a display+scene (+optional subchannel).

    Falls back to 404 if no record.
    """
    svc = DisplayImagePersistenceService(db)
    rec = _get_persisted_image_record(svc, _display_lookup_ids(db, display_id), scene_id, subchannel_id)
    if not rec:
        raise HTTPException(status_code=404, detail="No persisted image for display/scene")
    return {
        "id": rec.id,
        "display_id": rec.display_id,
        "scene_id": rec.scene_id,
        "subchannel_id": rec.subchannel_id,
        "assignment_id": rec.assignment_id,
        "image_url": rec.image_url,
        "thumbnail_url": _build_thumbnail_url(rec),
        "width": rec.width,
        "height": rec.height,
        "format": rec.format,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "source": rec.source,
    }


@router.get("/{display_id}/last-images", response_model=dict)
async def get_last_images_all_scenes(
    display_id: str,
    limit_per_scene: int = Query(1, ge=1, le=5),
    db: Session = Depends(get_db)
):
    """Return latest image records per scene for a display (optionally small history per scene)."""
    lookup_ids = _display_lookup_ids(db, display_id)
    rows = (
        db.query(DisplaySceneImage)
        .filter(DisplaySceneImage.display_id.in_(lookup_ids))
        .order_by(DisplaySceneImage.created_at.desc())
        .all()
    )
    grouped = {}
    for r in rows:
        key = (r.scene_id, r.subchannel_id)
        bucket = grouped.setdefault(key, [])
        if len(bucket) < limit_per_scene:
            bucket.append(r)
    result = []
    for (scene_id, subc), bucket in grouped.items():
        result.append({
            "scene_id": scene_id,
            "subchannel_id": subc,
            "images": [
                {
                    "id": rec.id,
                    "image_url": rec.image_url,
                    "thumbnail_url": _build_thumbnail_url(rec),
                    "width": rec.width,
                    "height": rec.height,
                    "format": rec.format,
                    "created_at": rec.created_at.isoformat() if rec.created_at else None,
                    "assignment_id": rec.assignment_id,
                } for rec in bucket
            ]
        })
    return {"display_id": display_id, "scenes": result}
