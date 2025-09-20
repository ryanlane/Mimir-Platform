"""
Display Client API Routes
Streamlined FastAPI router for display client management
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy import or_
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.db.base import SessionLocal
from app.db.models import DisplayClient, Scene
from app.schemas.displays import (
    DisplayClientRegistration, 
    DisplayClientResponse, 
    DisplayClientUpdate,
    DisplayClientListResponse,
)
from app.schemas.common import PaginationMeta
from app.services.mdns_discovery import mdns_discovery_service
from app.services.mqtt.publisher import mqtt_scene_service, mqtt_scene_assignment
from app.services.display_last_image import display_last_image_store
from app.config import settings
from pathlib import Path
from app.db.models import DisplaySceneImage
from app.services.display_image_persistence import DisplayImagePersistenceService


router = APIRouter(prefix="/displays", tags=["displays"])

class AssignSceneBody(BaseModel):
    scene_id: str
    subchannel_id: Optional[str] = None

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/status", response_model=dict)
async def get_displays_status(db: Session = Depends(get_db)):
    """Get overall display system status including mDNS discovered displays"""
    # Get displays from database
    db_displays = db.query(DisplayClient).all()
    db_online_count = len([d for d in db_displays if d.is_online])
    
    # Get discovered displays from mDNS service
    discovered_displays = []
    discovered_online_count = 0
    mdns_service_running = False
    
    if mdns_discovery_service.is_running:
        mdns_service_running = True
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        discovered_online_count = sum(1 for d in discovered_displays if d.is_online)
    
    # Combine totals (avoid double counting by using max)
    total_displays = max(len(db_displays), len(discovered_displays))
    total_online = max(db_online_count, discovered_online_count)
    
    # Enhanced status
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
            "service_available": mdns_discovery_service.is_available
        }
    }


# @router.post("/register", response_model=DisplayClientResponse)
# async def register_display_client(
#     registration: DisplayClientRegistration, 
#     db: Session = Depends(get_db)
# ):
#     """Register a new display client"""
    
#     # Check for existing display client with same hostname or name+location
#     existing_client = None
    
#     # First try to find by hostname if provided (most reliable)
#     if registration.hostname:
#         existing_client = db.query(DisplayClient).filter(
#             DisplayClient.hostname == registration.hostname
#         ).first()
    
#     # If not found by hostname, try name + location combination
#     if not existing_client:
#         existing_client = db.query(DisplayClient).filter(
#             DisplayClient.name == registration.name,
#             DisplayClient.location == registration.location
#         ).first()
    
#     if existing_client:
#         # Update existing client instead of creating new one
#         existing_client.name = registration.name
#         existing_client.location = registration.location
#         existing_client.hostname = registration.hostname
#         existing_client.webhook_port = registration.webhook_port
#         existing_client.width = registration.capabilities.resolution[0] if registration.capabilities.resolution else None
#         existing_client.height = registration.capabilities.resolution[1] if registration.capabilities.resolution and len(registration.capabilities.resolution) > 1 else None
#         existing_client.orientation = registration.capabilities.orientation
#         existing_client.client_version = registration.client_version
#         existing_client.redis_distribution = registration.capabilities.redis_distribution
#         existing_client.content_claiming = registration.capabilities.content_claiming
#         existing_client.display_type = "registered"
#         existing_client.discovery_method = "manual"
#         existing_client.auto_discovered = False
        
#         db.commit()
#         db.refresh(existing_client)
#         display_client = existing_client
#     else:
#         # Create new display client
#         import uuid
#         display_client = DisplayClient(
#             id=str(uuid.uuid4()),  # Generate a UUID for the new display
#             name=registration.name,
#             location=registration.location,
#             hostname=registration.hostname,
#             webhook_port=registration.webhook_port,
#             width=registration.capabilities.resolution[0] if registration.capabilities.resolution else None,
#             height=registration.capabilities.resolution[1] if registration.capabilities.resolution and len(registration.capabilities.resolution) > 1 else None,
#             orientation=registration.capabilities.orientation,
#             client_version=registration.client_version,
#             redis_distribution=registration.capabilities.redis_distribution,
#             content_claiming=registration.capabilities.content_claiming,
#             display_type="registered",
#             discovery_method="manual",
#             auto_discovered=False,
#             is_online=True,
#             last_seen=datetime.now(timezone.utc)
#         )
        
#         db.add(display_client)
#         db.commit()
#         db.refresh(display_client)
    
#     return DisplayClientResponse.model_validate(display_client)


@router.get("", response_model=DisplayClientListResponse)
async def list_display_clients(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_discovered: bool = Query(True, description="Include live discovered displays"),
    db: Session = Depends(get_db)
):
    """Get paginated list of display clients including discovered displays"""
    # Get displays from database
    db_clients = db.query(DisplayClient).offset(offset).limit(limit).all()
    display_responses = []
    
    # Add database displays
    for client in db_clients:
        display_responses.append(DisplayClientResponse.model_validate(client))
    
    # If requested, merge with discovered displays that aren't in database
    if include_discovered and mdns_discovery_service.is_running:
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        
        # Find discovered displays that aren't already in database
        db_hostnames = {client.hostname for client in db_clients if client.hostname}
        
        for discovered in discovered_displays:
            if discovered.hostname not in db_hostnames:
                try:
                    # Parse resolution
                    width, height = 800, 480  # defaults
                    if discovered.resolution:
                        try:
                            width, height = map(int, discovered.resolution.split("x"))
                        except ValueError:
                            pass
                    
                    # Create assigned scene object if scene data is available
                    assigned_scene = None
                    if discovered.assigned_scene_id:
                        assigned_scene = {
                            "id": discovered.assigned_scene_id,
                            "subchannel_id": discovered.assigned_subchannel_id
                        }

                    # Create a dict that matches DisplayClientResponse structure
                    discovered_dict = {
                        "id": discovered.display_id,
                        "name": discovered.display_name,
                        "location": discovered.location,
                        "hostname": discovered.hostname,
                        "webhook_port": discovered.webhook_port,
                        "client_version": discovered.client_version or "unknown",
                        "display_type": "discovered",
                        "discovery_method": "mdns",
                        "auto_discovered": True,
                        "width": width,
                        "height": height,
                        "orientation": discovered.properties.get("orientation", "landscape"),
                        "redis_distribution": discovered.properties.get("redis_distribution") == "true",
                        "content_claiming": discovered.properties.get("content_claiming") == "true",
                        "is_online": discovered.is_online,
                        "last_seen": discovered.last_seen,
                        "assigned_scene_id": assigned_scene,
                        "current_content_hash": None,
                        "created_at": discovered.discovered_at,
                        "updated_at": discovered.last_seen,
                        "tags": []
                    }
                    
                    # Create DisplayClientResponse from dict
                    discovered_response = DisplayClientResponse.model_validate(discovered_dict)
                    display_responses.append(discovered_response)
                    
                except Exception as e:
                    # Log error but continue
                    import logging
                    logging.getLogger(__name__).warning(f"Error adding discovered display {discovered.display_name}: {e}")
    
    # Get total count including potential discovered displays
    total_db = db.query(DisplayClient).count()
    total_discovered = 0
    
    if include_discovered and mdns_discovery_service.is_running:
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        # Get all hostnames from database to avoid duplicates
        all_db_hostnames = {client.hostname for client in db.query(DisplayClient).all() if client.hostname}
        total_discovered = sum(1 for d in discovered_displays if d.hostname not in all_db_hostnames)
    
    total = total_db + total_discovered
    
    return DisplayClientListResponse(
        data=display_responses,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
        total=total
    )


@router.get("/discovery/status")
async def get_discovery_status():
    """Get current mDNS discovery service status"""
    stats = mdns_discovery_service.get_discovery_stats()
    discovered = mdns_discovery_service.get_discovered_displays()
    
    return {
        "service_status": stats,
        "discovered_displays": [
            {
                "display_id": d.display_id,
                "display_name": d.display_name,
                "hostname": d.hostname,
                "location": d.location,
                "addresses": d.addresses,
                "is_online": d.is_online,
                "last_seen": d.last_seen.isoformat(),
                "discovered_at": d.discovered_at.isoformat()
            }
            for d in discovered
        ]
    }

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
    subchannel_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Return the persisted last image metadata for a display+scene (+optional subchannel).

    Falls back to 404 if no record.
    """
    svc = DisplayImagePersistenceService(db)
    rec = svc.get_last_for_display_scene(display_id, scene_id, subchannel_id)
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
    # Simple approach: query all rows for display then group in Python; for scale add SQL window function.
    rows = db.query(DisplaySceneImage).filter(DisplaySceneImage.display_id == display_id).order_by(DisplaySceneImage.created_at.desc()).all()
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


def _build_thumbnail_url(rec: DisplaySceneImage) -> Optional[str]:  # helper kept at bottom
    # If we stored a thumbnail path and it is under the configured root, map to public URL.
    if not rec.thumbnail_path:
        return None
    public_base = getattr(settings, "public_base_url", "")
    # If thumbnail_path already absolute inside public assets, just return guessed URL.
    # For now, treat stored_local_path parent relative: <public_base>/media/<...>
    # This could be refined with a dedicated configuration.
    path_obj = Path(rec.thumbnail_path)
    if path_obj.is_absolute():
        # Build relative suffix if inside working dir
        try:
            rel = path_obj.relative_to(Path.cwd())
            return f"{public_base}/{rel.as_posix()}" if public_base else f"/{rel.as_posix()}"
        except Exception:  # noqa: BLE001
            return rec.thumbnail_path
    return f"{public_base}/{rec.thumbnail_path}" if public_base else f"/{rec.thumbnail_path}"


@router.get("/discovery/live")
async def get_live_discovered_displays():
    """Get currently discovered displays from the live mDNS service"""
    if not mdns_discovery_service.is_running:
        raise HTTPException(
            status_code=503,
            detail="mDNS discovery service is not running."
        )
    
    discovered = mdns_discovery_service.get_discovered_displays()
    
    return {
        "total_discovered": len(discovered),
        "online_count": sum(1 for d in discovered if d.is_online),
        "discovered_displays": [
            {
                "service_name": d.service_name,
                "display_id": d.display_id,
                "display_name": d.display_name,
                "hostname": d.hostname,
                "location": d.location,
                "addresses": d.addresses,
                "webhook_port": d.webhook_port,
                "resolution": d.resolution,
                "client_version": d.client_version,
                "is_online": d.is_online,
                "discovered_at": d.discovered_at.isoformat(),
                "last_seen": d.last_seen.isoformat(),
                "properties": d.properties,
                "webhook_url": f"http://{d.addresses[0]}:{d.webhook_port}" if d.addresses and d.webhook_port else None
            }
            for d in discovered
        ]
    }


@router.get("/{display_id}", response_model=DisplayClientResponse)
async def get_display_client(display_id: str, db: Session = Depends(get_db)):
    """
    Get display client by ID. Supports both registered (database) and discovered (mDNS) displays.

    Args:
        display_id (str): The display's unique identifier.
        db (Session): Database session.

    Returns:
        DisplayClientResponse: Display client details.

    Raises:
        HTTPException: If display not found.
    """
    # Try database first
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if client:
        return DisplayClientResponse.model_validate(client)

    # Try discovered displays (mDNS)
    if mdns_discovery_service.is_running:
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        for discovered in discovered_displays:
            if discovered.display_id == display_id:
                # Parse resolution
                width, height = 800, 480  # defaults
                if discovered.resolution:
                    try:
                        width, height = map(int, discovered.resolution.split("x"))
                    except ValueError:
                        pass

                # Create assigned scene object if scene data is available
                assigned_scene = None
                if discovered.assigned_scene_id:
                    assigned_scene = {
                        "id": discovered.assigned_scene_id,
                        "subchannel_id": discovered.assigned_subchannel_id
                    }

                discovered_dict = {
                    "id": discovered.display_id,
                    "name": discovered.display_name,
                    "location": discovered.location,
                    "hostname": discovered.hostname,
                    "webhook_port": discovered.webhook_port,
                    "client_version": discovered.client_version or "unknown",
                    "display_type": "discovered",
                    "discovery_method": "mdns",
                    "auto_discovered": True,
                    "width": width,
                    "height": height,
                    "orientation": discovered.properties.get("orientation", "landscape"),
                    "redis_distribution": discovered.properties.get("redis_distribution") == "true",
                    "content_claiming": discovered.properties.get("content_claiming") == "true",
                    "is_online": discovered.is_online,
                    "last_seen": discovered.last_seen,
                    "assigned_scene_id": assigned_scene,
                    "current_content_hash": None,
                    "created_at": discovered.discovered_at,
                    "updated_at": discovered.last_seen,
                    "tags": []
                }
                return DisplayClientResponse.model_validate(discovered_dict)

    raise HTTPException(status_code=404, detail="Display client not found")


@router.put("/{display_id}", response_model=DisplayClientResponse)
async def update_display_client(
    display_id: str,
    update_data: DisplayClientUpdate,
    db: Session = Depends(get_db)
):
    """Update display client"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    
    db.commit()
    db.refresh(client)
    
    return DisplayClientResponse.model_validate(client)

# Since we have migrated to a more dynamic discovery and registration model,
# we are deprecating manual deletion of display clients to avoid accidental removals.

# @router.delete("/{display_id}")
# async def delete_display_client(display_id: str, db: Session = Depends(get_db)):
#     """Delete display client"""
#     client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
#     if not client:
#         raise HTTPException(status_code=404, detail="Display client not found")
    
#     db.delete(client)
#     db.commit()
    
#     return {"message": "Display client deleted successfully"}


# @router.put("/{display_id}/scene/{scene_id}")
# async def assign_scene_to_display(
#     display_id: str,
#     scene_id: int,
#     db: Session = Depends(get_db)
# ):
#     """Assign a scene to a display (MQTT set_scene command)"""
#     client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
#     if not client:
#         raise HTTPException(status_code=404, detail="Display client not found")
    
#     scene = db.query(Scene).filter(Scene.id == scene_id).first()
#     if not scene:
#         raise HTTPException(status_code=404, detail="Scene not found")
    
#     # Update database
#     client.assigned_scene_id = scene_id
#     client.scene_assigned_at = datetime.now(timezone.utc)
#     db.commit()

#     # MQTT assignment
#     assignment_id = f"set-{uuid.uuid4().hex[:8]}"
#     mqtt_success = False
#     if mqtt_scene_service.is_connected():
#         target_id = client.hostname or client.id
#         mqtt_success = await mqtt_scene_service.assign_scene_to_device(
#             device_id=target_id,
#             scene_id=str(scene_id),
#             assignment_id=assignment_id
#         )

#     return {
#         "message": f"Scene {scene_id} assigned to display {display_id}",
#         "scene_name": scene.name,
#         "assigned_at": client.scene_assigned_at.isoformat(),
#         "mqtt_assigned": mqtt_success,
#         "assignment_id": assignment_id,
#         "communication_method": getattr(client, 'communication_method', 'http')
#     }


@router.delete("/{display_id}/scene")
async def unassign_scene_from_display(display_id: str):
    """
    Unassign the scene from a display via MQTT.

    Args:
        display_id (str): The display's unique identifier.

    Returns:
        dict: Unassignment result.

    Raises:
        HTTPException: If display not found or MQTT fails.
    """
    if not mdns_discovery_service.is_running:
        raise HTTPException(status_code=503, detail="mDNS discovery service is not running")
    discovered_displays = mdns_discovery_service.get_discovered_displays()
    display = next((d for d in discovered_displays if d.display_id == display_id or d.hostname == display_id), None)
    if not display:
        raise HTTPException(status_code=404, detail=f"Display {display_id} not found")

    if not mqtt_scene_service.is_connected():
        raise HTTPException(status_code=503, detail="MQTT publisher not connected")

    assignment_id = f"clr-{uuid.uuid4().hex[:8]}"
    target_id = display.hostname or display.display_id
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
async def assign_scene_to_display(display_id: str, body: AssignSceneBody):
    """
    Assign a scene to a display via MQTT.
    
    Args:
        display_id (str): The display's unique identifier.
        body (AssignSceneBody): The scene assignment payload.
    
    Returns:
        dict: Assignment result.
    
    Raises:
        HTTPException: If display or scene not found, or MQTT fails.
    """
    # Find the display in discovered displays only
    if not mdns_discovery_service.is_running:
        raise HTTPException(status_code=503, detail="mDNS discovery service is not running")
    discovered_displays = mdns_discovery_service.get_discovered_displays()
    display = next((d for d in discovered_displays if d.display_id == display_id or d.hostname == display_id), None)
    if not display:
        raise HTTPException(status_code=404, detail=f"Display {display_id} not found")

    # Publish MQTT assign command
    if not mqtt_scene_service.is_connected():
        raise HTTPException(status_code=503, detail="MQTT publisher not connected")

    assignment_id = f"set-{uuid.uuid4().hex[:8]}"
    target_id = display.hostname or display.display_id
    
    # Update to include subchannel_id if the MQTT service supports it
    ok = await mqtt_scene_service.assign_scene_to_device(
        device_id=target_id,
        scene_id=str(body.scene_id),
        subchannel_id=body.subchannel_id,  # Add this parameter
        assignment_id=assignment_id
    )

    if not ok:
        raise HTTPException(status_code=502, detail="Failed to publish MQTT assignment")

    return {
        "ok": True,
        "display_id": display_id,
        "scene_id": body.scene_id,
        "subchannel_id": body.subchannel_id,  # Include in response
        "published_topic": f"mimir/{target_id}/cmd",
        "assignment_id": assignment_id
    }

@router.post("/discovery/start")
async def start_discovery_service():
    """Start the mDNS discovery service"""
    if mdns_discovery_service.is_running:
        return {"status": "already_running", "message": "mDNS discovery service is already running"}
    
    if not mdns_discovery_service.is_available:
        raise HTTPException(
            status_code=501,
            detail="mDNS discovery not available (zeroconf library not installed)"
        )
    
    success = await mdns_discovery_service.start_discovery()
    if success:
        return {"status": "started", "message": "mDNS discovery service started successfully"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to start mDNS discovery service"
        )


@router.post("/discovery/stop")
async def stop_discovery_service():
    """Stop the mDNS discovery service"""
    await mdns_discovery_service.stop_discovery()
    return {"status": "stopped", "message": "mDNS discovery service stopped"}


# @router.get("/unassigned")
# async def get_unassigned_displays(
#     include_discovered: bool = Query(True, description="Include discovered displays"),
#     db: Session = Depends(get_db)
# ):
#     """Get displays that don't have scene assignments"""
#     unassigned_displays = []
    
#     # Get unassigned database displays
#     db_displays = db.query(DisplayClient).filter(
#         DisplayClient.assigned_scene_id.is_(None)
#     ).all()
    
#     for client in db_displays:
#         unassigned_displays.append({
#             "display_id": client.id,
#             "display_name": client.name,
#             "location": client.location,
#             "hostname": client.hostname,
#             "display_type": "registered",
#             "is_online": client.is_online,
#             "last_seen": client.last_seen.isoformat() if client.last_seen else None,
#             "webhook_port": client.webhook_port,
#             "resolution": f"{client.width}x{client.height}" if client.width and client.height else None,
#             "client_version": client.client_version
#         })
    
#     # Add unassigned discovered displays if requested
#     if include_discovered and mdns_discovery_service.is_running:
#         discovered_displays = mdns_discovery_service.get_discovered_displays()
        
#         # Get assigned display IDs from database to filter out
#         assigned_db_hostnames = {
#             client.hostname for client in db.query(DisplayClient).filter(
#                 DisplayClient.assigned_scene_id.isnot(None)
#             ).all() if client.hostname
#         }
        
#         for discovered in discovered_displays:
#             # Skip if this discovered display is registered and assigned
#             if discovered.hostname not in assigned_db_hostnames:
#                 unassigned_displays.append({
#                     "display_id": discovered.display_id,
#                     "display_name": discovered.display_name,
#                     "location": discovered.location,
#                     "hostname": discovered.hostname,
#                     "display_type": "discovered",
#                     "is_online": discovered.is_online,
#                     "last_seen": discovered.last_seen.isoformat(),
#                     "discovered_at": discovered.discovered_at.isoformat(),
#                     "webhook_port": discovered.webhook_port,
#                     "resolution": discovered.resolution,
#                     "client_version": discovered.client_version
#                 })
    
#     return {
#         "total_unassigned": len(unassigned_displays),
#         "unassigned_displays": unassigned_displays
#     }
