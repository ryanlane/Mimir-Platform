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

"""Short-code pairing endpoints."""
import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import DisplayClient
from app.schemas.displays import (
    DisplayClientResponse,
    PairClaimRequest,
    PairStatusResponse,
)

from ._helpers import _build_client_config, _build_registered_display_response, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/pair/{code}/status", response_model=PairStatusResponse, tags=["pairing"])
async def get_pair_code_status(code: str):
    """Check whether a 6-character pairing code is pending and waiting to be claimed.

    Displays can poll this to show a 'waiting...' vs 'paired!' state without
    consuming the code.
    """
    from app.services.mqtt.pairing import pairing_service
    status = await pairing_service.get_pair_status(code)
    if not status:
        return PairStatusResponse(code=code.upper(), status="not_found")
    return PairStatusResponse(**status)


@router.post("/pair", response_model=DisplayClientResponse, tags=["pairing"])
async def claim_pair_code(body: PairClaimRequest, db: Session = Depends(get_db)):
    """Claim a 6-character pairing code to register a display.

    The display generates the code and shows it on screen (alongside a QR code).
    The user enters the code here; the API creates the display record and sends
    a finalize_registration command back to the display via MQTT.
    """
    from app.services.mqtt.pairing import pairing_service
    from app.services.mqtt.publisher import MQTTSceneAssignmentPublisher

    try:
        entry = await pairing_service.claim_pair(body.code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    device_id: str = entry["device_id"]
    capabilities: dict = entry.get("capabilities") or {}
    metadata: dict = entry.get("metadata") or {}

    name = body.name or metadata.get("name") or device_id
    location = body.location or metadata.get("location") or "Unknown"
    hostname = metadata.get("hostname") or device_id
    resolution = (
        capabilities.get("resolution")
        or capabilities.get("native_resolution")
        or [800, 480]
    )
    orientation = capabilities.get("orientation", "landscape")
    client_version = metadata.get("client_version", "unknown")

    existing = db.query(DisplayClient).filter(DisplayClient.hostname == hostname).first()
    if existing:
        existing.name = name
        existing.location = location
        existing.is_online = True
        existing.last_seen = datetime.now(timezone.utc)
        existing.client_version = client_version
        existing.orientation = orientation
        existing.discovery_method = "pairing_code"
        existing.redis_distribution = bool(capabilities.get("redis_distribution", False))
        existing.content_claiming = bool(capabilities.get("content_claiming", False))
        if "supports_animation" in capabilities:
            existing.supports_animation = bool(capabilities.get("supports_animation"))
        if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
            existing.width = int(resolution[0])
            existing.height = int(resolution[1])
        db.commit()
        db.refresh(existing)
        display = existing
    else:
        display = DisplayClient(
            id=str(uuid.uuid4()),
            name=name,
            location=location,
            hostname=hostname,
            display_type="registered",
            discovery_method="pairing_code",
            is_online=True,
            last_seen=datetime.now(timezone.utc),
            client_version=client_version,
            orientation=orientation,
            redis_distribution=bool(capabilities.get("redis_distribution", False)),
            content_claiming=bool(capabilities.get("content_claiming", False)),
            supports_animation=(
                bool(capabilities["supports_animation"])
                if "supports_animation" in capabilities else None
            ),
        )
        if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
            display.width = int(resolution[0])
            display.height = int(resolution[1])
        db.add(display)
        db.commit()
        db.refresh(display)

    client_config = _build_client_config(
        display_name=display.name,
        display_location=display.location or "",
        display_orientation=display.orientation,
    )

    reg_key = secrets.token_hex(16)
    try:
        publisher = MQTTSceneAssignmentPublisher.get()
        await publisher.finalize_registration(
            device_id=device_id,
            display_id=str(display.id),
            registration_key=reg_key,
            source="pairing_code",
            client_config=client_config,
        )
    except Exception as e:  # pragma: no cover - publish failure shouldn't fail the response
        logger.warning("Finalize registration publish failed device_id=%s err=%s", device_id, e)

    return DisplayClientResponse.model_validate(_build_registered_display_response(display))
