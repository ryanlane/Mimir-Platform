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
    """Get overall display system status"""
    displays = db.query(DisplayClient).all()
    online_count = len([d for d in displays if d.is_online])
    
    return {
        "total_displays": len(displays),
        "online_displays": online_count,
        "offline_displays": len(displays) - online_count,
        "status": "operational" if online_count > 0 else "no_displays"
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
    db: Session = Depends(get_db)
):
    """Get paginated list of display clients"""
    total = db.query(DisplayClient).count()
    clients = db.query(DisplayClient).offset(offset).limit(limit).all()
    
    display_responses = [DisplayClientResponse.model_validate(client) for client in clients]
    
    from app.schemas.common import PaginationMeta
    
    return DisplayClientListResponse(
        data=display_responses,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
        total=total
    )


@router.get("/discover")
async def discover_displays(
    timeout: int = Query(5, ge=1, le=30),
    auto_register: bool = Query(True),
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
        
        # Get auto-registered count from database
        auto_registered_count = 0
        if auto_register and mdns_discovery_service.auto_register:
            auto_registered_count = db.query(DisplayClient).filter(
                DisplayClient.discovery_method == "mdns",
                DisplayClient.auto_discovered == True
            ).count()
        
        return {
            "discovered_displays": discovered_displays,
            "auto_registered": [],  # Background service handles this automatically
            "discovery_timeout": 0,  # No timeout for background service
            "total_found": len(discovered_displays),
            "total_auto_registered": auto_registered_count,
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
        
        print(f"🔍 Starting mDNS discovery with timeout={timeout}, auto_register={auto_register}")
        
        discovered_displays = []
        auto_registered = []
        
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
                        
                        # Auto-register the display if requested
                        if auto_register:
                            try:
                                # Check if display already exists
                                existing = db.query(DisplayClient).filter(
                                    DisplayClient.hostname == hostname
                                ).first()
                                
                                if not existing:
                                    # Parse resolution from string like "800x480"
                                    resolution_str = properties.get("resolution", "800x480")
                                    try:
                                        resolution = [int(x) for x in resolution_str.split("x")]
                                        width = resolution[0]
                                        height = resolution[1]
                                    except:
                                        width = 800
                                        height = 480
                                    
                                    # Create new display client
                                    new_client = DisplayClient(
                                        id=display_id,
                                        name=display_name,
                                        location=properties.get("location", "Auto-discovered"),
                                        hostname=hostname,
                                        webhook_port=int(properties.get("webhook_port", 0)) if properties.get("webhook_port") else None,
                                        width=width,
                                        height=height,
                                        orientation=properties.get("orientation", "landscape"),
                                        client_version=properties.get("client_version", "unknown"),
                                        redis_distribution=properties.get("redis_distribution") == "true",
                                        content_claiming=properties.get("content_claiming") == "true",
                                        display_type="discovered",
                                        discovery_method="mdns",
                                        auto_discovered=True,
                                        is_online=True,
                                        last_seen=datetime.datetime.now()
                                    )
                                    
                                    db.add(new_client)
                                    db.commit()
                                    db.refresh(new_client)
                                    
                                    auto_registered.append({
                                        "display_id": display_id,
                                        "display_name": display_name,
                                        "hostname": hostname
                                    })
                                    print(f"✅ Auto-registered display: {display_name}")
                                else:
                                    # Update existing display
                                    existing.is_online = True
                                    existing.last_seen = datetime.datetime.now()
                                    existing.display_type = "discovered"
                                    existing.discovery_method = "mdns"
                                    db.commit()
                                    print(f"🔄 Updated existing display: {display_name}")
                                    
                            except Exception as e:
                                print(f"❌ Failed to auto-register {display_name}: {e}")
            
            def remove_service(self, zeroconf, service_type, name):
                pass
            
            def update_service(self, zeroconf, service_type, name):
                pass
        
        # Start discovery
        zeroconf = Zeroconf()
        listener = DisplayListener()
        
        # First, try to directly query the known service name pattern
        print("🔍 Directly querying for mimir display services...")
        try:
            # Try to get the specific service we found earlier
            service_name = "mimir-display-discovery-colorframe05-1756316347._mimir-display._tcp.local."
            info = zeroconf.get_service_info("_mimir-display._tcp.local.", service_name)
            if info:
                print(f"✅ Found direct service: {service_name}")
                listener.add_service(zeroconf, "_mimir-display._tcp.local.", service_name)
        except Exception as e:
            print(f"⚠️ Error querying direct service: {e}")
        
        # Also browse for services
        browser = ServiceBrowser(zeroconf, "_mimir-display._tcp.local.", listener)
        
        # Wait for discovery
        print(f"⏳ Waiting {timeout} seconds for services...")
        time.sleep(timeout)
        
        # Cleanup
        browser.cancel()
        zeroconf.close()
        
        print(f"✅ Discovery complete. Found {len(discovered_displays)} displays.")
        
        return {
            "discovered_displays": discovered_displays,
            "auto_registered": auto_registered if auto_register else [],
            "discovery_timeout": timeout,
            "total_found": len(discovered_displays),
            "total_auto_registered": len(auto_registered) if auto_register else 0,
            "discovery_completed_at": datetime.datetime.now().isoformat()
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
