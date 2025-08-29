"""
Display Client API Routes
FastAPI router for display client management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.db.base import SessionLocal
from app.db.models import DisplayClient, DisplayStatus, Scene, ContentLease
from app.schemas.displays import (
    DisplayClientRegistration, 
    DisplayClientResponse, 
    DisplayClientUpdate,
    DisplayClientListResponse,
    DisplayStatusResponse,
    DisplayCapabilities,
    SceneAssignment,
    ContentClaimRequest,
    ContentClaimResponse,
    AcknowledgmentRequest,
    LegacyDisplayStatusResponse
)
from app.schemas.common import PaginationParams
from app.services.mdns_discovery import mdns_discovery_service


router = APIRouter(prefix="/displays", tags=["displays"])


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
            last_seen=datetime.datetime.now()
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
    
    from app.schemas.common import PaginationMeta
    
    return DisplayClientListResponse(
        data=display_responses,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
        total=total
    )


@router.get("/discover")
async def discover_displays(
    timeout: int = Query(5, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """Discover available displays on network via mDNS"""
    # Check if continuous discovery is running
    if mdns_discovery_service.is_running:
        # Use the background service results
        discovered_displays = []
        for display in mdns_discovery_service.get_discovered_displays():
            display_info = {
                "service_name": display.service_name,
                "hostname": display.hostname,
                "display_name": display.display_name,
                "display_id": display.display_id,
                "location": display.location,
                "resolution": display.resolution,
                "client_version": display.client_version,
                "webhook_port": display.webhook_port,
                "addresses": display.addresses,
                "properties": display.properties,
                "discovered_at": display.discovered_at.isoformat(),
                "is_online": display.is_online
            }
            
            # Add webhook URL if available
            if display.addresses and display.webhook_port:
                display_info["webhook_url"] = f"http://{display.addresses[0]}:{display.webhook_port}"
            
            discovered_displays.append(display_info)
        
        return {
            "discovered_displays": discovered_displays,
            "discovery_timeout": 0,  # No timeout for background service
            "total_found": len(discovered_displays),
            "discovery_completed_at": datetime.datetime.now().isoformat(),
            "source": "background_service",
            "continuous_discovery": True
        }
    
    # Fallback to manual discovery if background service not running
    try:
        from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
        import time
        import threading
        import socket
        
        print(f"🔍 Starting manual mDNS discovery with timeout={timeout}")
        
        discovered_displays = []
        
        class DisplayListener(ServiceListener):
            def add_service(self, zeroconf, service_type, name):
                print(f"🔎 Found service: {name}")
                if '_mimir-display._tcp.local.' in name:
                    info = zeroconf.get_service_info(service_type, name)
                    if info:
                        print(f"✅ Got service info for: {name}")
                        
                        # Extract service properties
                        properties = {}
                        if info.properties:
                            for key, value in info.properties.items():
                                try:
                                    properties[key.decode('utf-8')] = value.decode('utf-8')
                                except:
                                    pass
                        
                        # Convert IP addresses to readable format
                        addresses = []
                        for addr in info.addresses:
                            try:
                                addresses.append(socket.inet_ntoa(addr))
                            except:
                                addresses.append(str(addr))
                        
                        hostname = properties.get("hostname", "unknown")
                        display_name = properties.get("display_name", f"Display ({hostname})")
                        display_id = properties.get("display_id", f"unknown-{hostname}")
                        
                        display_info = {
                            "service_name": name,
                            "hostname": hostname,
                            "display_name": display_name,
                            "display_id": display_id,
                            "location": properties.get("location", "Auto-discovered"),
                            "resolution": properties.get("resolution"),
                            "client_version": properties.get("client_version"),
                            "webhook_port": properties.get("webhook_port"),
                            "addresses": addresses,
                            "port": info.port,
                            "properties": properties,
                            "discovered_at": datetime.datetime.now().isoformat()
                        }
                        
                        # Add webhook URL if we have an address and port
                        if addresses and properties.get("webhook_port"):
                            display_info["webhook_url"] = f"http://{addresses[0]}:{properties.get('webhook_port')}"
                        
                        discovered_displays.append(display_info)
                        print(f"✅ Added display: {display_name} ({hostname}) at {addresses}")
            
            def remove_service(self, zeroconf, service_type, name):
                pass
            
            def update_service(self, zeroconf, service_type, name):
                pass
        
        # Start discovery
        zeroconf = Zeroconf()
        listener = DisplayListener()
        
        # Browse for services
        browser = ServiceBrowser(zeroconf, "_mimir-display._tcp.local.", listener)
        
        # Wait for discovery
        print(f"⏳ Waiting {timeout} seconds for services...")
        time.sleep(timeout)
        
        # Cleanup
        browser.cancel()
        zeroconf.close()
        
        print(f"✅ Manual discovery complete. Found {len(discovered_displays)} displays.")
        
        return {
            "discovered_displays": discovered_displays,
            "discovery_timeout": timeout,
            "total_found": len(discovered_displays),
            "discovery_completed_at": datetime.datetime.now().isoformat(),
            "source": "manual_discovery",
            "continuous_discovery": False
        }
        
    except ImportError:
        raise HTTPException(
            status_code=501, 
            detail="mDNS discovery not available (zeroconf library not installed)"
        )
    except Exception as e:
        print(f"❌ Discovery failed: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Discovery failed: {str(e)}"
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


@router.get("/discovery/live")
async def get_live_discovered_displays():
    """Get currently discovered displays from the live mDNS service"""
    if not mdns_discovery_service.is_running:
        raise HTTPException(
            status_code=503,
            detail="mDNS discovery service is not running. Use /api/displays/discovery/start to start it."
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
async def get_display_client(
    display_id: str,
    db: Session = Depends(get_db)
):
    """Get display client by ID"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    return DisplayClientResponse.model_validate(client)


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
async def delete_display_client(
    display_id: str,
    db: Session = Depends(get_db)
):
    """Delete display client"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    db.delete(client)
    db.commit()
    
    return {"message": "Display client deleted successfully"}


@router.post("/{display_id}/assign_scene")
async def assign_scene_to_display(
    display_id: str,
    assignment: SceneAssignment,
    db: Session = Depends(get_db)
):
    """Assign scene to display client"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    scene = db.query(Scene).filter(Scene.id == assignment.scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    client.assigned_scene_id = assignment.scene_id
    db.commit()
    
    return {"message": f"Scene {assignment.scene_id} assigned to display {display_id}"}


@router.delete("/{display_id}/assign_scene")
async def unassign_scene_from_display(
    display_id: str,
    db: Session = Depends(get_db)
):
    """Unassign scene from display client"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    client.assigned_scene_id = None
    db.commit()
    
    return {"message": f"Scene unassigned from display {display_id}"}


@router.get("/{display_id}/status", response_model=Optional[DisplayStatusResponse])
async def get_display_status(
    display_id: str,
    db: Session = Depends(get_db)
):
    """Get display status"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    status = db.query(DisplayStatus).filter(DisplayStatus.display_client_id == display_id).first()
    if not status:
        return None
    
    return DisplayStatusResponse.model_validate(status)


@router.post("/{display_id}/claim_content", response_model=ContentClaimResponse)
async def claim_content(
    display_id: str,
    claim_request: ContentClaimRequest,
    db: Session = Depends(get_db)
):
    """Claim content for display"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Create content lease
    lease = ContentLease(
        scene_id=claim_request.scene_id,
        display_id=display_id,
        content_id=claim_request.content_id,
        assignment_id=claim_request.assignment_id,
        status="active",
        assigned_at=datetime.datetime.now(),
        expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),  # 1 hour lease
        distribution_mode="claim"
    )
    
    db.add(lease)
    db.commit()
    db.refresh(lease)
    
    return ContentClaimResponse(
        lease_id=lease.lease_id,
        content_id=lease.content_id,
        expires_at=lease.expires_at,
        assignment_id=lease.assignment_id
    )


@router.post("/{display_id}/acknowledge")
async def acknowledge_content(
    display_id: str,
    lease_data: dict,
    db: Session = Depends(get_db)
):
    """Acknowledge content receipt"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    lease_id = lease_data.get("lease_id")
    if lease_id:
        lease = db.query(ContentLease).filter(ContentLease.lease_id == lease_id).first()
        if lease:
            lease.acknowledged_at = datetime.datetime.now()
            lease.status = "acknowledged"
            db.commit()
    
    return {"message": "Content acknowledged"}


@router.post("/{display_id}/refresh")
async def refresh_display(
    display_id: str,
    db: Session = Depends(get_db)
):
    """Refresh display content"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # This would trigger a refresh via webhook or WebSocket
    # For now, just return success
    return {"message": f"Refresh triggered for display {display_id}"}


@router.post("/{display_id}/update")
async def update_display_content(
    display_id: str,
    update_data: dict,
    db: Session = Depends(get_db)
):
    """Update display content"""
    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Update content hash if provided
    if "content_hash" in update_data:
        client.current_content_hash = update_data["content_hash"]
        client.last_seen = datetime.datetime.now()
        db.commit()
    
    return {"message": f"Display {display_id} content updated"}
