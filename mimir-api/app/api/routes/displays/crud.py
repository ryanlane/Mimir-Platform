"""Core display CRUD endpoints (list, get, update, delete, status)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import ContentLease, DisplayClient, DisplaySceneImage
from app.schemas.displays import (
    DisplayClientListResponse,
    DisplayClientResponse,
    DisplayClientUpdate,
)
from app.schemas.common import PaginationMeta
from app.services.display_last_image import display_last_image_store
from app.services.mdns_discovery import mdns_discovery_service
from app.services.scene_refresh_service import scene_refresh_service
from app.config import settings
from ._helpers import (
    get_db,
    _find_discovered_display,
    _push_runtime_display_config,
    _normalize_display_orientation,
    _native_dimensions_from_logical,
    _logical_dimensions_for_orientation,
    _parse_resolution,
    _extract_orientation,
    _build_discovered_display_response,
    _build_registered_display_response,
)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=dict)
async def get_displays_status(db: Session = Depends(get_db)):
    """Get overall display system status including mDNS discovered displays"""
    db_displays = db.query(DisplayClient).all()
    db_online_count = len([d for d in db_displays if d.is_online])

    discovered_displays = []
    discovered_online_count = 0
    mdns_service_running = False

    if mdns_discovery_service.is_running:
        mdns_service_running = True
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        discovered_online_count = sum(1 for d in discovered_displays if d.is_online)

    total_displays = max(len(db_displays), len(discovered_displays))
    total_online = max(db_online_count, discovered_online_count)

    status = "no_displays"
    if total_online > 0:
        status = "operational"
    elif total_displays > 0:
        status = "displays_offline"

    return {
        "total_displays": total_displays,
        "online_displays": total_online,
        "offline_displays": total_displays - total_online,
        "status": status,
        "database_displays": {
            "total": len(db_displays),
            "online": db_online_count,
            "offline": len(db_displays) - db_online_count
        },
        "discovered_displays": {
            "total": len(discovered_displays),
            "online": discovered_online_count,
            "offline": len(discovered_displays) - discovered_online_count
        },
        "mdns_discovery": {
            "service_running": mdns_service_running,
            "service_available": mdns_discovery_service.is_available,
            "external_feed_enabled": bool(getattr(settings, "mdns_external_feed_enabled", False)),
            "external_feed_token_required": bool(getattr(settings, "mdns_external_feed_token", None)),
        }
    }


@router.get("/", response_model=DisplayClientListResponse)
async def list_display_clients(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_discovered: bool = Query(True, description="Include live discovered displays"),
    db: Session = Depends(get_db)
):
    """Get paginated list of display clients including discovered displays"""
    db_clients = db.query(DisplayClient).offset(offset).limit(limit).all()

    discovered_displays = []
    discovered_addr_map: dict[str, list[str]] = {}
    if include_discovered and mdns_discovery_service.is_running:
        try:
            discovered_displays = mdns_discovery_service.get_discovered_displays()
            for d in discovered_displays:
                if getattr(d, 'hostname', None):
                    addrs = getattr(d, 'addresses', None) or []
                    if isinstance(addrs, (list, tuple)):
                        discovered_addr_map[d.hostname] = list(addrs)
        except Exception:  # pragma: no cover - defensive
            discovered_displays = []
            discovered_addr_map = {}

    display_responses: list[DisplayClientResponse] = []

    for client in db_clients:
        resp = DisplayClientResponse.model_validate(_build_registered_display_response(client))
        if client.hostname and client.hostname in discovered_addr_map:
            addrs = discovered_addr_map[client.hostname]
            if addrs:
                try:
                    resp.ip_addresses = addrs
                    resp.ip_address = addrs[0]
                except Exception:
                    data = resp.model_dump()
                    data['ip_addresses'] = addrs
                    data['ip_address'] = addrs[0]
                    resp = DisplayClientResponse.model_validate(data)
        display_responses.append(resp)

    if include_discovered and discovered_displays:
        db_hostnames = {client.hostname for client in db_clients if client.hostname}

        for discovered in discovered_displays:
            if discovered.hostname not in db_hostnames:
                try:
                    display_responses.append(
                        DisplayClientResponse.model_validate(_build_discovered_display_response(discovered))
                    )
                except Exception as e:  # pragma: no cover - defensive logging
                    logger.warning(
                        "Error adding discovered display %s: %s", getattr(discovered, 'display_name', 'unknown'), e
                    )

    total_db = db.query(DisplayClient).count()
    total_discovered = 0
    if include_discovered and discovered_displays:
        all_db_hostnames = {client.hostname for client in db.query(DisplayClient).all() if client.hostname}
        total_discovered = sum(1 for d in discovered_displays if d.hostname not in all_db_hostnames)

    total = total_db + total_discovered

    return DisplayClientListResponse(
        data=display_responses,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
        total=total
    )


@router.get("/{display_id}", response_model=DisplayClientResponse)
async def get_display_client(display_id: str, db: Session = Depends(get_db)):
    """Get display client by ID. Supports both registered (database) and discovered (mDNS) displays."""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if client:
        return DisplayClientResponse.model_validate(_build_registered_display_response(client))

    if mdns_discovery_service.is_running:
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        for discovered in discovered_displays:
            if discovered.display_id == display_id:
                return DisplayClientResponse.model_validate(_build_discovered_display_response(discovered))

    raise HTTPException(status_code=404, detail="Display client not found")


@router.put("/{display_id}", response_model=DisplayClientResponse)
async def update_display_client(
    display_id: str,
    update_data: DisplayClientUpdate,
    db: Session = Depends(get_db)
):
    """Update display client"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    discovered = _find_discovered_display(display_id, client.hostname if client else None)
    if not client and not discovered:
        raise HTTPException(status_code=404, detail="Display client not found")

    updates = update_data.model_dump(exclude_unset=True)
    requested_orientation = updates.get("orientation")
    normalized_orientation = _normalize_display_orientation(requested_orientation) if requested_orientation else None
    runtime_config_applied = False

    if client:
        if normalized_orientation:
            native_w, native_h = _native_dimensions_from_logical(client.width, client.height, client.orientation)
            new_w, new_h = _logical_dimensions_for_orientation(native_w, native_h, normalized_orientation)
            client.orientation = normalized_orientation
            if new_w and new_h:
                client.width = new_w
                client.height = new_h
            updates.pop("orientation", None)

        for key, value in updates.items():
            setattr(client, key, value)

        db.commit()
        db.refresh(client)
    elif normalized_orientation:
        width, height = _parse_resolution(discovered)
        native_w, native_h = _native_dimensions_from_logical(width, height, _extract_orientation(discovered, width, height))
        new_w, new_h = _logical_dimensions_for_orientation(native_w, native_h, normalized_orientation)
        discovered.properties["orientation"] = normalized_orientation
        discovered.properties["rotation_deg"] = "180" if normalized_orientation == "landscape_inverted" else discovered.properties.get("rotation_deg", "0")
        if new_w and new_h:
            discovered.properties["resolution"] = f"{new_w}x{new_h}"
            discovered.resolution = discovered.properties["resolution"]
        if "name" in updates and updates["name"]:
            discovered.display_name = updates["name"]
        if "location" in updates and updates["location"] is not None:
            discovered.location = updates["location"]

    if discovered and (normalized_orientation or "name" in updates or "location" in updates):
        try:
            await _push_runtime_display_config(
                discovered,
                orientation=normalized_orientation,
                display_name=(client.name if client else updates.get("name") or discovered.display_name),
                display_location=(client.location if client else updates.get("location") if "location" in updates else discovered.location),
            )
            runtime_config_applied = True
        except HTTPException as exc:
            if not client:
                raise
            logger.warning(
                "Display %s update saved but runtime config could not be pushed immediately: %s",
                display_id,
                exc.detail,
            )

    if client and client.assigned_scene_id and normalized_orientation and runtime_config_applied:
        target_device = client.hostname or client.id
        try:
            await scene_refresh_service.refresh_scene(
                client.assigned_scene_id,
                trigger_reason="display_config_update",
                force=True,
                target_devices=[target_device],
            )
        except Exception as exc:
            logger.warning("Scene refresh after orientation update failed for %s: %s", display_id, exc)

    if client:
        return DisplayClientResponse.model_validate(_build_registered_display_response(client))

    return DisplayClientResponse.model_validate(_build_discovered_display_response(discovered))


@router.delete("/{display_id}")
async def delete_display_client(display_id: str, db: Session = Depends(get_db)):
    """Delete a registered display from the service side.

    This is the service-side reset path for a device that has been wiped or
    needs to be re-paired. If the device is still discoverable over mDNS after
    deletion, it will reappear in the UI as an unpaired discovered display.
    """
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")

    deleted_leases = db.query(ContentLease).filter(ContentLease.display_id == display_id).delete(synchronize_session=False)
    deleted_images = db.query(DisplaySceneImage).filter(DisplaySceneImage.display_id == display_id).delete(synchronize_session=False)
    db.delete(client)
    db.commit()

    display_last_image_store.delete(display_id)

    return {
        "message": "Display client deleted successfully",
        "display_id": display_id,
        "deleted_content_leases": deleted_leases,
        "deleted_image_records": deleted_images,
    }
