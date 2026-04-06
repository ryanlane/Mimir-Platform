"""
Multi-Display Client Architecture for Mimir API

This implements a complete multi-display client system where:
1. Display clients register and identify themselves
2. Scenes can be assigned to specific display clients
3. WebSocket broadcasts are targeted to specific displays
4. Administrative interface for managing display assignments
"""

from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from fastapi import HTTPException, Depends
import uuid

# =============================================================================
# DATABASE SCHEMA EXTENSIONS
# =============================================================================

class DisplayClient(Base):
    """Represents a connected display client"""
    __tablename__ = "display_clients"
    
    id = Column(String, primary_key=True, index=True)  # UUID
    name = Column(String, nullable=False)  # Human-readable name
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)  # Physical location
    
    # Client capabilities
    resolution = Column(JSON, nullable=True)  # [width, height]
    supported_formats = Column(JSON, nullable=True)  # ["jpg", "png", "gif"]
    rotation = Column(String, default="landscape")  # "landscape", "portrait"
    
    # Connection status
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, default=func.now())
    websocket_connection_id = Column(String, nullable=True)
    
    # Current assignment
    assigned_scene_id = Column(String, ForeignKey("scenes.id"), nullable=True)
    
    # Configuration
    settings = Column(JSON, nullable=True)  # Display-specific settings
    tags = Column(JSON, nullable=True)  # ["lobby", "conference-room", "kiosk"]
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DisplayGroup(Base):
    """Groups of display clients for bulk operations"""
    __tablename__ = "display_groups"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Group settings
    display_client_ids = Column(JSON, nullable=True)  # List of client IDs
    default_scene_id = Column(String, ForeignKey("scenes.id"), nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class DisplayClientCapabilities(BaseModel):
    resolution: List[int]  # [width, height]
    supported_formats: List[str]  # ["jpg", "png", "gif"]
    rotation: str = "landscape"


class DisplayClientRegistration(BaseModel):
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    capabilities: DisplayClientCapabilities
    tags: Optional[List[str]] = None


class DisplayClientUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    tags: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None


class DisplayClientResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    location: Optional[str]
    is_online: bool
    last_seen: str
    assigned_scene_id: Optional[str]
    assigned_scene_name: Optional[str]
    resolution: Optional[List[int]]
    rotation: str
    tags: Optional[List[str]]


class SceneAssignment(BaseModel):
    scene_id: Optional[str]  # None to unassign


class DisplayGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    display_client_ids: List[str]
    default_scene_id: Optional[str] = None


# =============================================================================
# ENHANCED CONNECTION MANAGER
# =============================================================================

class MultiDisplayConnectionManager:
    """Enhanced connection manager with display client awareness"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}  # connection_id -> websocket
        self.display_clients: Dict[str, str] = {}    # display_client_id -> connection_id
        self.sequence_id = 0
    
    async def register_display_client(self, websocket: WebSocket, display_client_id: str):
        """Register a display client with specific ID"""
        connection_id = str(uuid.uuid4())
        
        await websocket.accept()
        self.connections[connection_id] = websocket
        self.display_clients[display_client_id] = connection_id
        
        # Update database status
        db = SessionLocal()
        try:
            client = db.query(DisplayClient).filter(DisplayClient.id == display_client_id).first()
            if client:
                client.is_online = True
                client.last_seen = datetime.now()
                client.websocket_connection_id = connection_id
                db.commit()
        finally:
            db.close()
            
        return connection_id
    
    async def connect_anonymous(self, websocket: WebSocket):
        """Connect anonymous client (web dashboard, etc.)"""
        connection_id = str(uuid.uuid4())
        await websocket.accept()
        self.connections[connection_id] = websocket
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Disconnect and cleanup"""
        if connection_id in self.connections:
            del self.connections[connection_id]
            
        # Find and cleanup display client mapping
        for display_id, conn_id in list(self.display_clients.items()):
            if conn_id == connection_id:
                del self.display_clients[display_id]
                
                # Update database status
                db = SessionLocal()
                try:
                    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
                    if client:
                        client.is_online = False
                        client.websocket_connection_id = None
                        db.commit()
                finally:
                    db.close()
                break
    
    async def send_to_display_client(self, display_client_id: str, message: dict):
        """Send message to specific display client"""
        connection_id = self.display_clients.get(display_client_id)
        if connection_id and connection_id in self.connections:
            websocket = self.connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message))
                return True
            except:
                self.disconnect(connection_id)
                return False
        return False
    
    async def send_to_display_group(self, display_client_ids: List[str], message: dict):
        """Send message to multiple display clients"""
        results = {}
        for client_id in display_client_ids:
            results[client_id] = await self.send_to_display_client(client_id, message)
        return results
    
    async def broadcast_to_all_displays(self, message: dict):
        """Broadcast to all connected display clients"""
        display_results = {}
        for display_id in self.display_clients.keys():
            display_results[display_id] = await self.send_to_display_client(display_id, message)
        return display_results
    
    async def broadcast_to_dashboard_clients(self, message: dict):
        """Broadcast to dashboard/admin clients (non-display clients)"""
        dashboard_connections = []
        for conn_id, websocket in self.connections.items():
            if conn_id not in self.display_clients.values():
                dashboard_connections.append(websocket)
        
        for websocket in dashboard_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except:
                # Find and disconnect
                for conn_id, ws in self.connections.items():
                    if ws == websocket:
                        self.disconnect(conn_id)
                        break


# =============================================================================
# API ENDPOINTS
# =============================================================================

# Global manager instance
multi_display_manager = MultiDisplayConnectionManager()

@app.post("/api/displays/register", response_model=DisplayClientResponse)
async def register_display_client(
    registration: DisplayClientRegistration, 
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Register a new display client"""
    
    # Generate unique ID
    display_id = str(uuid.uuid4())
    
    # Create display client record
    display_client = DisplayClient(
        id=display_id,
        name=registration.name,
        description=registration.description,
        location=registration.location,
        resolution=registration.capabilities.resolution,
        supported_formats=registration.capabilities.supported_formats,
        rotation=registration.capabilities.rotation,
        tags=registration.tags,
        is_online=False
    )
    
    db.add(display_client)
    db.commit()
    db.refresh(display_client)
    
    # Broadcast new display registration
    await broadcast_event("display_client_registered", {
        "displayId": display_id,
        "name": registration.name,
        "location": registration.location,
        "capabilities": registration.capabilities.dict()
    })
    
    return DisplayClientResponse(
        id=display_client.id,
        name=display_client.name,
        description=display_client.description,
        location=display_client.location,
        is_online=display_client.is_online,
        last_seen=display_client.last_seen.isoformat(),
        assigned_scene_id=display_client.assigned_scene_id,
        assigned_scene_name=None,
        resolution=display_client.resolution,
        rotation=display_client.rotation,
        tags=display_client.tags
    )


@app.get("/api/displays", response_model=List[DisplayClientResponse])
async def list_display_clients(
    online_only: bool = False,
    location: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """List all display clients with optional filtering"""
    
    query = db.query(DisplayClient)
    
    if online_only:
        query = query.filter(DisplayClient.is_online == True)
    
    if location:
        query = query.filter(DisplayClient.location.ilike(f"%{location}%"))
    
    if tag:
        query = query.filter(DisplayClient.tags.contains([tag]))
    
    clients = query.all()
    
    # Get scene names for assigned scenes
    scene_names = {}
    if clients:
        scene_ids = [c.assigned_scene_id for c in clients if c.assigned_scene_id]
        if scene_ids:
            scenes = db.query(Scene).filter(Scene.id.in_(scene_ids)).all()
            scene_names = {s.id: s.name for s in scenes}
    
    return [
        DisplayClientResponse(
            id=client.id,
            name=client.name,
            description=client.description,
            location=client.location,
            is_online=client.is_online,
            last_seen=client.last_seen.isoformat(),
            assigned_scene_id=client.assigned_scene_id,
            assigned_scene_name=scene_names.get(client.assigned_scene_id),
            resolution=client.resolution,
            rotation=client.rotation,
            tags=client.tags
        ) for client in clients
    ]


@app.post("/api/displays/{display_id}/assign_scene")
async def assign_scene_to_display(
    display_id: str,
    assignment: SceneAssignment,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Assign a scene to a specific display client"""
    
    # Get display client
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Validate scene exists (if assigning)
    scene = None
    if assignment.scene_id:
        scene = db.query(Scene).filter(Scene.id == assignment.scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
    
    # Update assignment
    old_scene_id = display_client.assigned_scene_id
    display_client.assigned_scene_id = assignment.scene_id
    db.commit()
    
    # Send targeted WebSocket message to the specific display
    scene_assignment_message = {
        "event": "scene_assigned",
        "data": {
            "displayId": display_id,
            "sceneId": assignment.scene_id,
            "sceneName": scene.name if scene else None,
            "previousSceneId": old_scene_id,
            "timestamp": datetime.now().isoformat()
        },
        "timestamp": datetime.now().isoformat(),
        "sequenceId": multi_display_manager.sequence_id + 1
    }
    
    # Send to specific display client
    sent = await multi_display_manager.send_to_display_client(display_id, scene_assignment_message)
    
    # Also broadcast to dashboard clients for monitoring
    await multi_display_manager.broadcast_to_dashboard_clients({
        "event": "display_assignment_updated",
        "data": {
            "displayId": display_id,
            "displayName": display_client.name,
            "newSceneId": assignment.scene_id,
            "newSceneName": scene.name if scene else None,
            "previousSceneId": old_scene_id
        },
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "message": f"Scene assignment updated for display {display_client.name}",
        "assigned_scene": scene.name if scene else None,
        "message_sent": sent
    }


@app.websocket("/ws/display/{display_id}")
async def display_websocket_endpoint(websocket: WebSocket, display_id: str):
    """WebSocket endpoint for specific display clients"""
    
    # Verify display client exists
    db = SessionLocal()
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    db.close()
    
    if not display_client:
        await websocket.close(code=4004, reason="Display client not found")
        return
    
    # Register the display client connection
    connection_id = await multi_display_manager.register_display_client(websocket, display_id)
    
    try:
        # Send initial state to display client
        await send_display_initial_state(websocket, display_id)
        
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle display client messages
                try:
                    message = json.loads(data)
                    await handle_display_client_message(display_id, message, websocket)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "data": {"message": "Invalid JSON format"},
                        "timestamp": datetime.now().isoformat()
                    }))
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_text(json.dumps({
                    "event": "ping",
                    "data": {"timestamp": datetime.now().isoformat()},
                    "timestamp": datetime.now().isoformat()
                }))
                
    except Exception as e:
        print(f"Display WebSocket error for {display_id}: {e}")
    finally:
        multi_display_manager.disconnect(connection_id)


async def send_display_initial_state(websocket: WebSocket, display_id: str):
    """Send initial state specific to a display client"""
    db = SessionLocal()
    try:
        display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
        
        assigned_scene = None
        if display_client.assigned_scene_id:
            assigned_scene = db.query(Scene).filter(Scene.id == display_client.assigned_scene_id).first()
        
        initial_state = {
            "event": "display_connection_established",
            "data": {
                "displayId": display_id,
                "displayName": display_client.name,
                "assignedScene": {
                    "id": assigned_scene.id if assigned_scene else None,
                    "name": assigned_scene.name if assigned_scene else None,
                    "channels": assigned_scene.channels if assigned_scene else []
                } if assigned_scene else None,
                "capabilities": {
                    "resolution": display_client.resolution,
                    "rotation": display_client.rotation,
                    "supported_formats": display_client.supported_formats
                },
                "serverTime": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        await websocket.send_text(json.dumps(initial_state))
        
    finally:
        db.close()


async def handle_display_client_message(display_id: str, message: dict, websocket: WebSocket):
    """Handle messages from display clients"""
    
    event_type = message.get("event")
    
    if event_type == "ping":
        # Respond to ping
        await websocket.send_text(json.dumps({
            "event": "pong",
            "data": {"timestamp": datetime.now().isoformat()},
            "timestamp": datetime.now().isoformat()
        }))
        
    elif event_type == "display_status_update":
        # Update display status
        data = message.get("data", {})
        
        # Broadcast status update to dashboard clients
        await multi_display_manager.broadcast_to_dashboard_clients({
            "event": "display_status_updated",
            "data": {
                "displayId": display_id,
                "status": data,
                "timestamp": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        })
        
    elif event_type == "request_scene_refresh":
        # Display client requesting scene refresh
        db = SessionLocal()
        try:
            display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
            if display_client and display_client.assigned_scene_id:
                await send_display_initial_state(websocket, display_id)
        finally:
            db.close()


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@app.post("/api/displays/bulk_assign")
async def bulk_assign_scene(
    display_ids: List[str],
    assignment: SceneAssignment,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Assign the same scene to multiple display clients"""
    
    results = {}
    
    for display_id in display_ids:
        try:
            # This reuses the single assignment logic
            result = await assign_scene_to_display(display_id, assignment, db)
            results[display_id] = {"success": True, "message": result["message"]}
        except Exception as e:
            results[display_id] = {"success": False, "error": str(e)}
    
    return {
        "message": f"Bulk assignment completed for {len(display_ids)} displays",
        "results": results
    }


# Integration with existing scene activation
async def enhanced_scene_activation(scene_id: str, target_displays: Optional[List[str]] = None):
    """Enhanced scene activation with display targeting"""
    
    db = SessionLocal()
    try:
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # If no target displays specified, get all displays assigned to this scene
        if target_displays is None:
            assigned_displays = db.query(DisplayClient).filter(
                DisplayClient.assigned_scene_id == scene_id,
                DisplayClient.is_online == True
            ).all()
            target_displays = [d.id for d in assigned_displays]
        
        # Send activation message to target displays
        activation_message = {
            "event": "scene_activated",
            "data": {
                "sceneId": scene_id,
                "sceneName": scene.name,
                "channels": scene.channels or [],
                "overlay": scene.overlay,
                "timestamp": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        results = await multi_display_manager.send_to_display_group(target_displays, activation_message)
        
        return {
            "message": f"Scene {scene.name} activated on {len(target_displays)} displays",
            "target_displays": target_displays,
            "delivery_results": results
        }
        
    finally:
        db.close()


# Add this to your existing scene activation endpoint
@app.post("/api/scenes/{scene_id}/activate_on_displays")
async def activate_scene_on_specific_displays(
    scene_id: str,
    display_ids: List[str],
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Activate a scene on specific display clients"""
    
    return await enhanced_scene_activation(scene_id, display_ids)
