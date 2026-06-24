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

"""Scene assignment endpoints for displays."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DisplayClient
from app.services.mdns_discovery import mdns_discovery_service
from app.services.mqtt.publisher import mqtt_scene_assignment, mqtt_scene_service
from app.services.scene_refresh_service import scene_refresh_service

from ._helpers import (
    _normalize_public_host_hint,
    _platform_url_for_clients,
    build_http_url,
    get_db,
)
from ._schemas import AssignSceneBody

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("/{display_id}/scene")
async def unassign_scene_from_display(display_id: str):
    """Unassign the scene from a display via MQTT."""
    if not mdns_discovery_service.is_running:
        raise HTTPException(status_code=503, detail="mDNS discovery service is not running")
    discovered_displays = mdns_discovery_service.get_discovered_displays()
    display = next((d for d in discovered_displays if d.display_id == display_id or d.hostname == display_id), None)
    if not display:
        raise HTTPException(status_code=404, detail=f"Display {display_id} not found")

    if not mqtt_scene_service.is_connected():
        raise HTTPException(status_code=503, detail="MQTT publisher not connected")

    assignment_id = f"clr-{uuid.uuid4().hex[:8]}"
    target_id = getattr(display, "display_id", None) or getattr(display, "hostname", None) or display_id
    ok = await mqtt_scene_assignment.clear_scene(
        device_id=target_id
    )

    if not ok:
        raise HTTPException(status_code=502, detail="Failed to publish MQTT unassignment")

    return {
        "ok": True,
        "display_id": display_id,
        "published_topic": f"mimir/{target_id}/cmd",
        "assignment_id": assignment_id
    }


@router.post("/{display_id}/scene")
async def assign_scene_to_display(
    display_id: str,
    body: AssignSceneBody,
    request: Request,
    db: Session = Depends(get_db),
):
    """Assign a scene to a display via MQTT."""
    discovered_display = None
    if mdns_discovery_service.is_running:
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        discovered_display = next(
            (d for d in discovered_displays if d.display_id == display_id or d.hostname == display_id),
            None,
        )

    db_display = db.query(DisplayClient).filter(
        (DisplayClient.id == display_id) | (DisplayClient.hostname == display_id)
    ).first()

    if not discovered_display and not db_display:
        raise HTTPException(status_code=404, detail=f"Display {display_id} not found")

    if not mqtt_scene_service.is_connected():
        raise HTTPException(status_code=503, detail="MQTT publisher not connected")

    assignment_id = f"set-{uuid.uuid4().hex[:8]}"
    target_id = (
        getattr(discovered_display, "display_id", None)
        or getattr(discovered_display, "hostname", None)
        or getattr(db_display, "hostname", None)
        or getattr(db_display, "id", None)
        or display_id
    )

    ok = await mqtt_scene_service.assign_scene_to_device(
        device_id=target_id,
        scene_id=str(body.scene_id),
        subchannel_id=body.subchannel_id,
        assignment_id=assignment_id
    )

    if not ok:
        raise HTTPException(status_code=502, detail="Failed to publish MQTT assignment")

    if discovered_display:
        discovered_display.assigned_scene_id = str(body.scene_id)
        discovered_display.assigned_subchannel_id = body.subchannel_id

    if db_display:
        db_display.assigned_scene_id = str(body.scene_id)
        db_display.content_variant = body.content_variant
        db.commit()

    refresh_targets = list({
        candidate
        for candidate in [
            target_id,
            getattr(discovered_display, "display_id", None),
            getattr(discovered_display, "hostname", None),
            getattr(db_display, "id", None),
            getattr(db_display, "hostname", None),
        ]
        if candidate
    })

    public_host_hint = _normalize_public_host_hint(body.public_host_hint)
    refresh_result = await scene_refresh_service.refresh_scene(
        str(body.scene_id),
        trigger_reason="display_assignment",
        force=True,
        target_devices=refresh_targets,
        public_base_url_override=(
            build_http_url(public_host_hint, settings.public_port or settings.api_port)
            if public_host_hint
            else _platform_url_for_clients(request)
        ),
    )

    if refresh_result.status != "ok":
        logger.warning(
            "display.assign.initial_refresh status=%s display=%s scene=%s skipped=%s errors=%s targets=%s",
            refresh_result.status,
            display_id,
            body.scene_id,
            refresh_result.skipped_reason,
            refresh_result.errors,
            refresh_targets,
        )

    return {
        "ok": True,
        "display_id": display_id,
        "scene_id": body.scene_id,
        "subchannel_id": body.subchannel_id,
        "content_variant": body.content_variant,
        "published_topic": f"mimir/{target_id}/cmd",
        "assignment_id": assignment_id,
        "initial_refresh": refresh_result.to_dict(),
    }
