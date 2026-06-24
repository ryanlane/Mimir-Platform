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

"""Discovery API Routes (MQTT Heartbeat-based)

Endpoints (initial phase - read + approve + reject):
GET /displays/discovery
POST /displays/discovery/{device_id}/approve
POST /displays/discovery/{device_id}/reject
GET /displays/discovery/stats

Feature guarded by settings.mqtt_discovery_enabled.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import DisplayClient  # type: ignore
from app.services.mqtt.discovery_registry import mqtt_discovery_registry

logger = get_logger(__name__)

router = APIRouter(prefix="/displays/discovery", tags=["discovery"])

class DiscoveryDevice(BaseModel):
    device_id: str
    state: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    last_heartbeat: datetime | None = None
    capabilities: dict | None = None
    display_id: str | None = None
    conflict: bool = False
    hardware_fingerprint: str | None = None
    offline_since: datetime | None = None

class DiscoveryListResponse(BaseModel):
    devices: list[DiscoveryDevice]
    count: int

class ApproveBody(BaseModel):
    name: str | None = Field(None, description="Human friendly name")
    location: str | None = Field(None, description="Physical location/label")

class RejectBody(BaseModel):
    reason: str | None = None

@router.get("", response_model=DiscoveryListResponse)
async def list_discovered_devices(states: str | None = None):
    if not settings.mqtt_discovery_enabled:
        raise HTTPException(status_code=404, detail="MQTT discovery disabled")
    state_filter = states.split(',') if states else None
    records = await mqtt_discovery_registry.list_devices(state_filter)
    devices: list[DiscoveryDevice] = []
    for r in records:
        devices.append(DiscoveryDevice(
            device_id=r.get("device_id"),
            state=r.get("state"),
            first_seen=_parse_dt(r.get("first_seen")),
            last_seen=_parse_dt(r.get("last_seen")),
            last_heartbeat=_parse_dt(r.get("last_heartbeat")),
            capabilities=r.get("capabilities"),
            display_id=r.get("display_id"),
            conflict=bool(int(r.get("conflict", 0))) if isinstance(r.get("conflict"), str) else bool(r.get("conflict", 0)),
            hardware_fingerprint=r.get("hardware_fingerprint"),
            offline_since=_parse_dt(r.get("offline_since")),
        ))
    return DiscoveryListResponse(devices=devices, count=len(devices))

@router.post("/{device_id}/approve", response_model=DiscoveryDevice)
async def approve_device(device_id: str, body: ApproveBody):
    if not settings.mqtt_discovery_enabled:
        raise HTTPException(status_code=404, detail="MQTT discovery disabled")
    rec = await mqtt_discovery_registry.get(device_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Device not found")
    if rec.get("state") == "registered" and rec.get("display_id"):
        # Already registered - return as-is
        return _rec_to_model(rec)

    # Create DB DisplayClient row and finalize registration
    db = SessionLocal()
    try:
        # Basic duplicate check by hardware fingerprint if present
        hwfp = rec.get("hardware_fingerprint")
        if hwfp:
            existing = db.query(DisplayClient).filter(DisplayClient.hardware_fingerprint == hwfp).first()  # type: ignore[attr-defined]
            if existing:
                # Promote registry entry to registered mapping existing
                await mqtt_discovery_registry.promote_to_registered(device_id, existing.id)
                rec = await mqtt_discovery_registry.get(device_id) or rec
                return _rec_to_model(rec)

        display = DisplayClient(
            id=str(uuid.uuid4()),
            name=body.name or f"Display {device_id[:6]}",
            location=body.location,
            hostname=None,  # Unknown via pure MQTT path
            discovery_method="mqtt",
            auto_discovered=True,
            display_type="registered",
            is_online=True,
            last_seen=datetime.utcnow(),
        )
        # Optional capability enrichment
        caps = rec.get("capabilities") or {}
        if isinstance(caps, dict):
            res = caps.get("resolution")
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                display.width = int(res[0])
                display.height = int(res[1])
            if caps.get("orientation"):
                display.orientation = caps.get("orientation")
            if caps.get("client_version"):
                display.client_version = caps.get("client_version")
            if "redis_distribution" in caps:
                display.redis_distribution = bool(caps.get("redis_distribution"))
            if "content_claiming" in caps:
                display.content_claiming = bool(caps.get("content_claiming"))
        # Hardware fingerprint field (if model supports it; ignore if not present)
        if hasattr(display, 'hardware_fingerprint') and rec.get("hardware_fingerprint"):
            display.hardware_fingerprint = rec.get("hardware_fingerprint")  # type: ignore[attr-defined]

        db.add(display)
        db.commit()
        db.refresh(display)
        # Generate opaque registration key
        registration_key = secrets.token_urlsafe(24)
        await mqtt_discovery_registry.set_registration_key(device_id, registration_key)
        await mqtt_discovery_registry.promote_to_registered(device_id, display.id)

        # Send finalize_registration command via publisher
        try:
            from app.services.mqtt.publisher import MQTTSceneAssignmentPublisher
            publisher = MQTTSceneAssignmentPublisher.get()
            await publisher.finalize_registration(device_id, display.id, registration_key)
        except Exception as pub_exc:  # pragma: no cover
            # Publishing failure does not roll back DB; device can still function & retry later.
            logger.warning("Finalize registration publish failed device_id=%s err=%s", device_id, pub_exc)

        rec = await mqtt_discovery_registry.get(device_id) or rec
        return _rec_to_model(rec)
    except Exception as e:
        db.rollback()
        logger.error("Approve device failed device_id=%s err=%s", device_id, e)
        raise HTTPException(status_code=500, detail="Failed to approve device") from e
    finally:
        db.close()

@router.post("/{device_id}/reject")
async def reject_device(device_id: str, body: RejectBody):
    if not settings.mqtt_discovery_enabled:
        raise HTTPException(status_code=404, detail="MQTT discovery disabled")
    rec = await mqtt_discovery_registry.get(device_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Device not found")
    # Hard delete ephemeral record
    # (Direct internal call; no public delete yet in registry—simulate via sweep by forcing expired TTL logic)
    # Simpler for now: treat as expired by removing from in-memory or Redis
    try:
        deleted = await mqtt_discovery_registry.delete(device_id)  # type: ignore[attr-defined]
        if not deleted:
            logger.info("Reject device requested but already absent device_id=%s", device_id)
    except Exception as e:  # pragma: no cover
        logger.warning("Reject device delete failed device_id=%s err=%s", device_id, e)
    return {"status": "rejected", "device_id": device_id, "reason": body.reason}

@router.get("/stats", response_model=dict)
async def discovery_stats():
    if not settings.mqtt_discovery_enabled:
        raise HTTPException(status_code=404, detail="MQTT discovery disabled")
    records = await mqtt_discovery_registry.list_devices()
    counts = {}
    for r in records:
        counts[r.get("state")] = counts.get(r.get("state"), 0) + 1
    return {"counts": counts, "total": len(records)}

# -------- Helpers --------

def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return None


def _rec_to_model(rec: dict) -> DiscoveryDevice:
    return DiscoveryDevice(
        device_id=rec.get("device_id"),
        state=rec.get("state"),
        first_seen=_parse_dt(rec.get("first_seen")),
        last_seen=_parse_dt(rec.get("last_seen")),
        last_heartbeat=_parse_dt(rec.get("last_heartbeat")),
        capabilities=rec.get("capabilities"),
        display_id=rec.get("display_id"),
        conflict=bool(int(rec.get("conflict", 0))) if isinstance(rec.get("conflict"), str) else bool(rec.get("conflict", 0)),
        hardware_fingerprint=rec.get("hardware_fingerprint"),
        offline_since=_parse_dt(rec.get("offline_since")),
    )
