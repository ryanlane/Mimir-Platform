"""
Display Client API Routes
Streamlined FastAPI router for display client management
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy import or_
from datetime import datetime, timezone
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
from app.services.mqtt.publisher import mqtt_scene_service


router = APIRouter(prefix="/displays", tags=["displays"])

class AssignSceneBody(BaseModel):
    scene_id: str

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


@router.post("/register", response_model=DisplayClientResponse)
async def register_display_client(
    registration: DisplayClientRegistration, 
    db: Session = Depends(get_db)
):
    """Register a new display client"""
    
    # Check for existing display client with same hostname or name+location
    existing_client = None
    
    # First try to find by hostname if provided (most reliable)
    if registration.hostname:
        existing_client = db.query(DisplayClient).filter(
            DisplayClient.hostname == registration.hostname
        ).first()
    
    # If not found by hostname, try name + location combination
    if not existing_client:
        existing_client = db.query(DisplayClient).filter(
            DisplayClient.name == registration.name,
            DisplayClient.location == registration.location
        ).first()
    
    if existing_client:
        # Update existing client instead of creating new one
        existing_client.name = registration.name
        existing_client.location = registration.location
        existing_client.hostname = registration.hostname
        existing_client.webhook_port = registration.webhook_port
        existing_client.width = registration.capabilities.resolution[0] if registration.capabilities.resolution else None
        existing_client.height = registration.capabilities.resolution[1] if registration.capabilities.resolution and len(registration.capabilities.resolution) > 1 else None
        existing_client.orientation = registration.capabilities.orientation
        existing_client.client_version = registration.client_version
        existing_client.redis_distribution = registration.capabilities.redis_distribution
        existing_client.content_claiming = registration.capabilities.content_claiming
        existing_client.display_type = "registered"
        existing_client.discovery_method = "manual"
        existing_client.auto_discovered = False
        
        db.commit()
        db.refresh(existing_client)
        display_client = existing_client
    else:
        # Create new display client
        import uuid
        display_client = DisplayClient(
            id=str(uuid.uuid4()),  # Generate a UUID for the new display
            name=registration.name,
            location=registration.location,
            hostname=registration.hostname,
            webhook_port=registration.webhook_port,
            width=registration.capabilities.resolution[0] if registration.capabilities.resolution else None,
            height=registration.capabilities.resolution[1] if registration.capabilities.resolution and len(registration.capabilities.resolution) > 1 else None,
            orientation=registration.capabilities.orientation,
            client_version=registration.client_version,
            redis_distribution=registration.capabilities.redis_distribution,
            content_claiming=registration.capabilities.content_claiming,
            display_type="registered",
            discovery_method="manual",
            auto_discovered=False,
            is_online=True,
            last_seen=datetime.now(timezone.utc)
        )
        
        db.add(display_client)
        db.commit()
        db.refresh(display_client)
    
    return DisplayClientResponse.model_validate(display_client)


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
                        "assigned_scene_id": None,
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
                    "assigned_scene_id": None,
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


@router.delete("/{display_id}")
async def delete_display_client(display_id: str, db: Session = Depends(get_db)):
    """Delete display client"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    db.delete(client)
    db.commit()
    
    return {"message": "Display client deleted successfully"}


@router.put("/{display_id}/scene/{scene_id}")
async def assign_scene_to_display(
    display_id: str,
    scene_id: int,
    db: Session = Depends(get_db)
):
    """Assign a scene to a display (MQTT set_scene command)"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Update database
    client.assigned_scene_id = scene_id
    client.scene_assigned_at = datetime.now(timezone.utc)
    db.commit()

    # MQTT assignment
    assignment_id = f"set-{uuid.uuid4().hex[:8]}"
    mqtt_success = False
    if mqtt_scene_service.is_connected():
        target_id = client.hostname or client.id
        mqtt_success = await mqtt_scene_service.assign_scene_to_device(
            device_id=target_id,
            scene_id=str(scene_id),
            assignment_id=assignment_id
        )

    return {
        "message": f"Scene {scene_id} assigned to display {display_id}",
        "scene_name": scene.name,
        "assigned_at": client.scene_assigned_at.isoformat(),
        "mqtt_assigned": mqtt_success,
        "assignment_id": assignment_id,
        "communication_method": getattr(client, 'communication_method', 'http')
    }


@router.delete("/{display_id}/scene")
async def unassign_scene_from_display(
    display_id: str,
    db: Session = Depends(get_db)
):
    """Unassign scene from a display (MQTT clear_scene command)"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    current_scene_id = client.assigned_scene_id
    client.assigned_scene_id = None
    client.scene_assigned_at = None
    db.commit()

    # MQTT unassignment
    assignment_id = f"clr-{uuid.uuid4().hex[:8]}"
    mqtt_success = False
    if mqtt_scene_service.is_connected():
        target_id = client.hostname or client.id
        mqtt_success = await mqtt_scene_service.clear_scene_on_device(
            device_id=target_id,
            assignment_id=assignment_id
        )

    return {
        "message": f"Scene unassigned from display {display_id}",
        "previous_scene_id": current_scene_id,
        "mqtt_unassigned": mqtt_success,
        "assignment_id": assignment_id,
        "communication_method": getattr(client, 'communication_method', 'http')
    }


@router.post("/{display_id}/scene")
async def post_assign_scene(display_id: str, body: AssignSceneBody):
    """Assign a scene to a display (MQTT push) using JSON body."""
    db = SessionLocal()
    try:
        # Look up scene
        scene = db.query(Scene).filter(Scene.id == body.scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail=f"Scene {body.scene_id} not found")

        # Look up display by id OR hostname (supports discovered vs. registered)
        display = db.query(DisplayClient).filter(
            or_(DisplayClient.id == display_id, DisplayClient.hostname == display_id)
        ).first()
        if not display:
            raise HTTPException(status_code=404, detail=f"Display {display_id} not found")

        # Persist assignment immediately so UI reflects it
        display.assigned_scene_id = body.scene_id
        display.scene_assigned_at = datetime.now(timezone.utc)
        db.commit()

        # Publish MQTT assign command
        
        if not mqtt_scene_service.is_connected():
            raise HTTPException(status_code=503, detail="MQTT publisher not connected")

        # Use hostname if present (your device topics use the hostname today)
        target_id = display.hostname or display.id
        ok = await mqtt_scene_service.assign_scene_to_device(
            device_id=target_id,
            scene_id=str(body.scene_id)
        )

        if not ok:
            raise HTTPException(status_code=502, detail="Failed to publish MQTT assignment")

        return {
            "ok": True,
            "display_id": display_id,
            "scene_id": body.scene_id,
            "published_topic": f"mimir/{target_id}/cmd"
        }
    finally:
        db.close()

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


@router.get("/unassigned")
async def get_unassigned_displays(
    include_discovered: bool = Query(True, description="Include discovered displays"),
    db: Session = Depends(get_db)
):
    """Get displays that don't have scene assignments"""
    unassigned_displays = []
    
    # Get unassigned database displays
    db_displays = db.query(DisplayClient).filter(
        DisplayClient.assigned_scene_id.is_(None)
    ).all()
    
    for client in db_displays:
        unassigned_displays.append({
            "display_id": client.id,
            "display_name": client.name,
            "location": client.location,
            "hostname": client.hostname,
            "display_type": "registered",
            "is_online": client.is_online,
            "last_seen": client.last_seen.isoformat() if client.last_seen else None,
            "webhook_port": client.webhook_port,
            "resolution": f"{client.width}x{client.height}" if client.width and client.height else None,
            "client_version": client.client_version
        })
    
    # Add unassigned discovered displays if requested
    if include_discovered and mdns_discovery_service.is_running:
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        
        # Get assigned display IDs from database to filter out
        assigned_db_hostnames = {
            client.hostname for client in db.query(DisplayClient).filter(
                DisplayClient.assigned_scene_id.isnot(None)
            ).all() if client.hostname
        }
        
        for discovered in discovered_displays:
            # Skip if this discovered display is registered and assigned
            if discovered.hostname not in assigned_db_hostnames:
                unassigned_displays.append({
                    "display_id": discovered.display_id,
                    "display_name": discovered.display_name,
                    "location": discovered.location,
                    "hostname": discovered.hostname,
                    "display_type": "discovered",
                    "is_online": discovered.is_online,
                    "last_seen": discovered.last_seen.isoformat(),
                    "discovered_at": discovered.discovered_at.isoformat(),
                    "webhook_port": discovered.webhook_port,
                    "resolution": discovered.resolution,
                    "client_version": discovered.client_version
                })
    
    return {
        "total_unassigned": len(unassigned_displays),
        "unassigned_displays": unassigned_displays
    }
