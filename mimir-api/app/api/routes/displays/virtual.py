"""Virtual display endpoints for developer/debug mode.

Virtual displays are synthetic DisplayClient records that appear in the Screens
view exactly like real displays. They exist only in the DB, have no real MQTT
connection, and are always marked online. Useful for testing scene assignment
and program logic without physical hardware.

Only available when DEBUG=true.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ContentLease, DisplayClient, DisplaySceneImage
from app.services.display_last_image import display_last_image_store

from ._helpers import get_db

router = APIRouter()

RESOLUTION_PRESETS: dict[str, tuple[int, int, str]] = {
    "landscape_800x480":   (800,  480,  "landscape"),
    "portrait_480x800":    (480,  800,  "portrait"),
    "landscape_1280x720":  (1280, 720,  "landscape"),
    "portrait_720x1280":   (720,  1280, "portrait"),
    "square_600x600":      (600,  600,  "square"),
    "landscape_1872x1404": (1872, 1404, "landscape"),
    "landscape_960x540":   (960,  540,  "landscape"),
}


def _guard():
    if not settings.debug:
        raise HTTPException(
            status_code=403,
            detail="Virtual displays are only available in debug/developer mode (DEBUG=true)",
        )


class CreateVirtualDisplayBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    location: str = Field("Virtual", max_length=128)
    preset: str = Field("landscape_800x480")
    width: int | None = Field(None, gt=0, le=10000)
    height: int | None = Field(None, gt=0, le=10000)


@router.get("/virtual/presets")
async def list_virtual_presets():
    """List available resolution presets for virtual displays."""
    _guard()
    return {
        "presets": [
            {"id": k, "label": f"{v[2].capitalize()} {v[0]}×{v[1]}", "width": v[0], "height": v[1], "orientation": v[2]}
            for k, v in RESOLUTION_PRESETS.items()
        ]
    }


@router.post("/virtual")
async def create_virtual_display(
    body: CreateVirtualDisplayBody,
    db: Session = Depends(get_db),
):
    """Create a virtual display for development. DEBUG=true required."""
    _guard()

    if body.width and body.height:
        w, h = body.width, body.height
        orientation = "square" if w == h else ("portrait" if h > w else "landscape")
    elif body.preset in RESOLUTION_PRESETS:
        w, h, orientation = RESOLUTION_PRESETS[body.preset]
    else:
        raise HTTPException(400, f"Unknown preset '{body.preset}'. Available: {list(RESOLUTION_PRESETS)}")

    display_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    display = DisplayClient(
        id=display_id,
        name=body.name,
        location=body.location,
        display_type="registered",
        discovery_method="virtual",
        auto_discovered=False,
        hostname=f"virtual-{display_id[:8]}",
        width=w,
        height=h,
        orientation=orientation,
        is_online=True,
        last_seen=now,
        created_at=now,
    )
    db.add(display)
    db.commit()
    db.refresh(display)

    return {
        "ok": True,
        "display_id": display_id,
        "name": display.name,
        "location": display.location,
        "width": w,
        "height": h,
        "orientation": orientation,
        "discovery_method": "virtual",
    }


@router.delete("/virtual/{display_id}")
async def delete_virtual_display(display_id: str, db: Session = Depends(get_db)):
    """Delete a virtual display. Only virtual displays can be removed via this endpoint."""
    _guard()

    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(404, "Display not found")
    if client.discovery_method != "virtual":
        raise HTTPException(
            400,
            "This endpoint only removes virtual displays. Use the standard unpair flow for real displays.",
        )

    db.query(ContentLease).filter(ContentLease.display_id == display_id).delete(synchronize_session=False)
    db.query(DisplaySceneImage).filter(DisplaySceneImage.display_id == display_id).delete(synchronize_session=False)
    db.delete(client)
    db.commit()

    display_last_image_store.delete(display_id)

    return {"ok": True, "display_id": display_id}
