from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime
import json
import asyncio

# Database setup
DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Models
class Channel(Base):
    __tablename__ = "channels"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    version = Column(String, default="1.0.0")
    settings_type = Column(String, default="simple")
    config_schema = Column(JSON, nullable=True)
    current_settings = Column(JSON, nullable=True)
    status = Column(JSON, nullable=True)
    rel_logo_image_path = Column(String, nullable=True)

class Scene(Base):
    __tablename__ = "scenes"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    channels = Column(JSON)
    image_fit = Column(String, default="cover")
    overlay = Column(JSON, nullable=True)
    schedule = Column(JSON, nullable=True)
    theme = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)

class Overlay(Base):
    __tablename__ = "overlays"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    channel = Column(JSON, nullable=True)
    path_root = Column(String, nullable=True)

class DisplayStatus(Base):
    __tablename__ = "display_status"
    id = Column(Integer, primary_key=True, index=True)
    hardware = Column(JSON)
    current_scene = Column(String, nullable=True)
    current_image = Column(JSON, nullable=True)
    resolution = Column(JSON)

# Create tables
Base.metadata.create_all(bind=engine)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.sequence_id = 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def get_next_sequence_id(self) -> int:
        self.sequence_id += 1
        return self.sequence_id

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        message_str = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_full_state(self, websocket: WebSocket, db: Session):
        """Send complete current state to a newly connected client"""
        try:
            # Get current active scene
            active_scene = db.query(Scene).filter(Scene.is_active == True).first()
            
            # Get all scenes
            all_scenes = db.query(Scene).all()
            
            # Get all channels
            channels = db.query(Channel).all()
            
            # Get display status
            display_status = db.query(DisplayStatus).first()
            
            full_state = {
                "event": "connection_established",
                "data": {
                    "connectionId": f"conn_{datetime.datetime.now().timestamp()}",
                    "currentState": {
                        "displayStatus": {
                            "currentScene": active_scene.id if active_scene else None,
                            "currentSceneName": active_scene.name if active_scene else None,
                            "hardware": display_status.hardware if display_status else {
                                "type": "mock", "resolution": [800, 600], "available": True
                            },
                            "resolution": display_status.resolution if display_status else [800, 600]
                        },
                        "activeScenes": [s.id for s in all_scenes if s.is_active],
                        "allScenes": [
                            {
                                "id": s.id,
                                "name": s.name,
                                "isActive": s.is_active,
                                "channels": s.channels or []
                            } for s in all_scenes
                        ],
                        "channels": [
                            {
                                "id": c.id,
                                "name": c.name,
                                "status": c.status or {"lastUpdate": None, "lastError": None, "usingFallback": False}
                            } for c in channels
                        ]
                    },
                    "serverInfo": {
                        "version": "1.0",
                        "connectedClients": len(self.active_connections),
                        "serverTime": datetime.datetime.now().isoformat()
                    }
                },
                "timestamp": datetime.datetime.now().isoformat(),
                "sequenceId": self.get_next_sequence_id()
            }
            
            await self.send_personal_message(json.dumps(full_state), websocket)
            
        except Exception as e:
            print(f"Error sending full state: {e}")
            # Send basic connection confirmation as fallback
            await self.send_personal_message(
                json.dumps({
                    "event": "connected",
                    "data": {"message": "WebSocket connection established"},
                    "timestamp": datetime.datetime.now().isoformat()
                }),
                websocket
            )

async def broadcast_error(error_code: str, message: str, context: Dict[str, Any] = None):
    """Broadcast error events to all connected clients"""
    await broadcast_event("error", {
        "code": error_code,
        "message": message,
        "context": context or {},
        "recovery": {
            "action": "check_logs",
            "timestamp": datetime.datetime.now().isoformat()
        }
    })

# Global connection manager instance
manager = ConnectionManager()

# WebSocket Event Models
class WebSocketEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

async def broadcast_event(event_type: str, data: Dict[str, Any], previous_state: Optional[Dict[str, Any]] = None):
    """Helper function to broadcast enhanced events to all connected clients"""
    enhanced_data = {
        **data,
        "triggeredBy": {
            "source": "api",
            "timestamp": datetime.datetime.now().isoformat()
        }
    }
    
    if previous_state:
        enhanced_data["previousState"] = previous_state
    
    event = {
        "event": event_type,
        "data": enhanced_data,
        "timestamp": datetime.datetime.now().isoformat(),
        "sequenceId": manager.get_next_sequence_id()
    }
    await manager.broadcast(event)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Models for API
class ChannelStatusModel(BaseModel):
    lastUpdate: Optional[str] = None
    lastError: Optional[str] = None
    usingFallback: Optional[bool] = False

class ChannelResponse(BaseModel):
    id: str
    name: str
    description: str
    relLogoImagePath: Optional[str] = None
    version: str = "1.0.0"
    settingsType: str = "simple"
    status: Optional[Dict[str, Any]] = None

class ChannelConfigResponse(BaseModel):
    name: str
    description: str
    settingsType: str
    settings: Optional[Dict[str, Any]] = None

class SceneOverlay(BaseModel):
    overlays: List[str]
    position: List[str]
    background: bool
    backgroundColor: Dict[str, int]

class SceneSchedule(BaseModel):
    days: List[str]
    start: str
    end: str

class SceneResponse(BaseModel):
    id: str
    name: str
    channels: List[str]
    overlay: Optional[SceneOverlay] = None
    schedule: Optional[SceneSchedule] = None
    isActive: Optional[bool] = False

class SceneCreateRequest(BaseModel):
    name: str
    channels: List[str]
    overlay: Optional[SceneOverlay] = None
    schedule: Optional[SceneSchedule] = None

class OverlayResponse(BaseModel):
    id: str
    name: str
    description: str
    channel: Optional[Dict[str, Any]] = None
    pathRoot: Optional[str] = None

class DisplayHardware(BaseModel):
    type: str
    resolution: List[int]
    available: bool

class DisplayImage(BaseModel):
    filename: str
    path: str
    width: int
    height: int
    uploadedAt: str

class DisplayStatusResponse(BaseModel):
    hardware: DisplayHardware
    currentScene: Optional[str] = None
    currentImage: Optional[DisplayImage] = None
    resolution: List[int]

class ImageRequestBody(BaseModel):
    resolution: List[int]
    orientation: str

class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int

class ErrorResponse(BaseModel):
    detail: str

# Initialize FastAPI app
app = FastAPI(title="Mimir Platform API", version="1.0")

# Add CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    db = SessionLocal()
    
    try:
        # Send full state snapshot on connection
        await manager.send_full_state(websocket, db)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client with timeout for heartbeat
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    message = json.loads(data)
                    
                    # Handle different client message types
                    if message.get("event") == "ping":
                        # Respond to ping with pong
                        pong_response = {
                            "event": "pong",
                            "data": {"timestamp": datetime.datetime.now().isoformat()},
                            "timestamp": datetime.datetime.now().isoformat()
                        }
                        await manager.send_personal_message(json.dumps(pong_response), websocket)
                        
                    elif message.get("event") == "state_sync_request":
                        # Handle state sync request
                        await manager.send_full_state(websocket, db)
                        
                    elif message.get("event") == "subscribe":
                        # Handle subscription management (future enhancement)
                        await manager.send_personal_message(
                            json.dumps({
                                "event": "subscription_confirmed",
                                "data": {"events": message.get("data", {}).get("events", [])},
                                "timestamp": datetime.datetime.now().isoformat()
                            }),
                            websocket
                        )
                    else:
                        # Echo back unknown messages for debugging
                        await manager.send_personal_message(f"Echo: {data}", websocket)
                        
                except json.JSONDecodeError:
                    # Handle non-JSON messages
                    await manager.send_personal_message(f"Echo: {data}", websocket)
                    
            except asyncio.TimeoutError:
                # Send heartbeat ping if no message received
                ping_message = {
                    "event": "ping",
                    "data": {"timestamp": datetime.datetime.now().isoformat()},
                    "timestamp": datetime.datetime.now().isoformat()
                }
                await manager.send_personal_message(json.dumps(ping_message), websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
    finally:
        db.close()

# Initialize database with sample data
def init_sample_data():
    db = SessionLocal()
    try:
        # Add sample channels if none exist
        if db.query(Channel).count() == 0:
            sample_channels = [
                Channel(
                    id="weather_channel",
                    name="Weather Channel",
                    description="Current weather by location",
                    version="1.0.0",
                    settings_type="simple",
                    rel_logo_image_path="static/logo.png",
                    config_schema={
                        "name": "Weather Display",
                        "description": "Shows current weather conditions",
                        "settingsType": "simple",
                        "settings": {
                            "api_key": {
                                "type": "string",
                                "required": True,
                                "secret": True,
                                "label": "API Key"
                            },
                            "location": {
                                "type": "string",
                                "required": True,
                                "default": "New York",
                                "label": "Location"
                            }
                        }
                    },
                    status={
                        "lastUpdate": "2025-08-18T10:30:00Z",
                        "lastError": None,
                        "usingFallback": False
                    }
                ),
                Channel(
                    id="example_channel",
                    name="Example Channel",
                    description="Sample photo display channel",
                    version="1.0.0",
                    settings_type="simple",
                    status={
                        "lastUpdate": "2025-08-18T10:30:00Z",
                        "lastError": None,
                        "usingFallback": False
                    }
                )
            ]
            for channel in sample_channels:
                db.add(channel)
        
        # Add sample overlays if none exist
        if db.query(Overlay).count() == 0:
            sample_overlays = [
                Overlay(
                    id="date",
                    name="Date",
                    description="Shows current date in Month DD, YYYY format",
                    channel=None,
                    path_root="static/"
                ),
                Overlay(
                    id="channel_overlay_example",
                    name="Channel Overlay Example",
                    description="Shows example data supplied by channel",
                    channel={
                        "channelId": "example_channel",
                        "channelName": "Example Channel",
                        "overlayPath": "channel/example_channel/overlay/channel_overlay_example"
                    },
                    path_root=None
                )
            ]
            for overlay in sample_overlays:
                db.add(overlay)
        
        # Add sample display status if none exists
        if db.query(DisplayStatus).count() == 0:
            display_status = DisplayStatus(
                hardware={
                    "type": "mock",
                    "resolution": [800, 600],
                    "available": True
                },
                current_scene=None,
                current_image=None,
                resolution=[800, 600]
            )
            db.add(display_status)
        
        db.commit()
    finally:
        db.close()

# Initialize sample data on startup
init_sample_data()

# API Endpoints

# Channels
@app.get("/api/channels")
async def list_channels(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    total = db.query(Channel).count()
    channels = db.query(Channel).offset(offset).limit(limit).all()
    
    result = [
        ChannelResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            relLogoImagePath=c.rel_logo_image_path,
            version=c.version,
            settingsType=c.settings_type,
            status=c.status
        ) for c in channels
    ]
    
    return {
        "channels": result,
        "meta": PaginationMeta(total=total, limit=limit, offset=offset)
    }

@app.get("/api/channels/{channel_id}/config")
async def get_channel_config(channel_id: str, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return channel.config_schema or {}

@app.get("/api/channels/{channel_id}/settings")
async def get_channel_settings(channel_id: str, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Return current settings or defaults from schema
    settings = channel.current_settings or {}
    if not settings and channel.config_schema and "settings" in channel.config_schema:
        for key, value in channel.config_schema["settings"].items():
            if "default" in value:
                settings[key] = value["default"]
    
    return {"settings": settings}

@app.post("/api/channels/{channel_id}/settings")
async def update_channel_settings(
    channel_id: str, 
    settings: Dict[str, Any], 
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Update settings
    channel.current_settings = settings
    
    # Update status to reflect settings change
    current_status = channel.status or {}
    current_status["lastSettingsUpdate"] = datetime.datetime.now().isoformat()
    channel.status = current_status
    
    db.commit()
    
    # Broadcast channel status update
    await broadcast_event("channel_status_update", {
        "channelId": channel_id,
        "channelName": channel.name,
        "status": {
            "active": True,
            "lastUpdate": current_status.get("lastUpdate"),
            "lastSettingsUpdate": current_status["lastSettingsUpdate"],
            "usingFallback": current_status.get("usingFallback", False),
            "lastError": current_status.get("lastError")
        },
        "settingsUpdated": True
    })
    
    return {"message": "Settings updated successfully"}

@app.post("/api/channels/{channel_id}/image_request")
async def request_channel_image(
    channel_id: str,
    request_body: ImageRequestBody,
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Update channel status
    current_status = channel.status or {}
    current_status["lastImageRequest"] = datetime.datetime.now().isoformat()
    current_status["lastError"] = None
    channel.status = current_status
    db.commit()
    
    # Broadcast channel status update
    await broadcast_event("channel_status_update", {
        "channelId": channel_id,
        "channelName": channel.name,
        "status": {
            "active": True,
            "lastUpdate": current_status["lastImageRequest"],
            "imageGenerated": True,
            "usingFallback": False,
            "lastError": None
        },
        "imageGenerated": True
    })
    
    # Mock image generation
    return {
        "success": True,
        "imagePath": f"/channels/{channel_id}/current.jpg",
        "message": "Test image generated successfully"
    }

# Scenes
@app.get("/api/scenes")
async def list_scenes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    total = db.query(Scene).count()
    scenes = db.query(Scene).offset(offset).limit(limit).all()
    
    result = [
        SceneResponse(
            id=s.id,
            name=s.name,
            channels=s.channels or [],
            overlay=s.overlay,
            schedule=s.schedule,
            isActive=s.is_active
        ) for s in scenes
    ]
    
    return {
        "scenes": result,
        "meta": PaginationMeta(total=total, limit=limit, offset=offset)
    }

@app.post("/api/scenes")
async def create_scene(scene_data: SceneCreateRequest, db: Session = Depends(get_db)):
    # Generate ID from name
    scene_id = scene_data.name.lower().replace(" ", "-")
    
    # Check if scene exists
    existing = db.query(Scene).filter(Scene.id == scene_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Scene with this name already exists")
    
    db_scene = Scene(
        id=scene_id,
        name=scene_data.name,
        channels=scene_data.channels,
        overlay=scene_data.overlay.dict() if scene_data.overlay else None,
        schedule=scene_data.schedule.dict() if scene_data.schedule else None,
        is_active=False
    )
    
    db.add(db_scene)
    db.commit()
    db.refresh(db_scene)
    
    # Broadcast WebSocket event
    await broadcast_event("scene_created", {
        "sceneId": scene_id,
        "sceneName": scene_data.name,
        "channels": scene_data.channels
    })
    
    return {
        "id": scene_id,
        "name": scene_data.name,
        "message": "Scene created successfully"
    }

@app.get("/api/scenes/{scene_id}")
async def get_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    return SceneResponse(
        id=scene.id,
        name=scene.name,
        channels=scene.channels or [],
        overlay=scene.overlay,
        schedule=scene.schedule,
        isActive=scene.is_active
    )

@app.put("/api/scenes/{scene_id}")
async def update_scene(
    scene_id: str, 
    scene_data: SceneCreateRequest, 
    db: Session = Depends(get_db)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    scene.name = scene_data.name
    scene.channels = scene_data.channels
    scene.overlay = scene_data.overlay.dict() if scene_data.overlay else None
    scene.schedule = scene_data.schedule.dict() if scene_data.schedule else None
    
    db.commit()
    
    # Broadcast WebSocket event
    await broadcast_event("scene_updated", {
        "sceneId": scene_id,
        "sceneName": scene_data.name,
        "channels": scene_data.channels
    })
    
    return {
        "id": scene_id,
        "name": scene_data.name,
        "message": "Scene updated successfully"
    }

@app.delete("/api/scenes/{scene_id}")
async def delete_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    scene_name = scene.name
    db.delete(scene)
    db.commit()
    
    # Broadcast WebSocket event
    await broadcast_event("scene_deleted", {
        "sceneId": scene_id,
        "sceneName": scene_name
    })
    
    return {"message": f"Scene {scene_id} deleted successfully"}

@app.post("/api/scenes/{scene_id}/activate")
async def activate_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Get previous active scene for context
    previous_scene = db.query(Scene).filter(Scene.is_active == True).first()
    
    # Deactivate all other scenes
    db.query(Scene).update({"is_active": False})
    
    # Activate this scene
    scene.is_active = True
    db.commit()
    
    # Get display status for enhanced event data
    display_status = db.query(DisplayStatus).first()
    
    # Broadcast enhanced WebSocket event
    await broadcast_event("scene_activated", {
        "sceneId": scene_id,
        "sceneName": scene.name,
        "channels": scene.channels or [],
        "previousScene": previous_scene.id if previous_scene else None,
        "previousSceneName": previous_scene.name if previous_scene else None,
        "displayUpdate": {
            "resolution": display_status.resolution if display_status else [800, 600],
            "hardware": display_status.hardware if display_status else {
                "type": "mock", "available": True
            }
        }
    })
    
    return {"message": f"Scene {scene_id} activated successfully"}

@app.post("/api/scenes/{scene_id}/deactivate")
async def deactivate_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    scene.is_active = False
    db.commit()
    
    # Broadcast enhanced WebSocket event
    await broadcast_event("scene_deactivated", {
        "sceneId": scene_id,
        "sceneName": scene.name,
        "channels": scene.channels or [],
        "displayUpdate": {
            "currentScene": None,
            "currentSceneName": None
        }
    })
    
    return {"message": f"Scene {scene_id} deactivated successfully"}

@app.post("/api/scenes/{scene_id}/display")
async def display_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Broadcast WebSocket event
    await broadcast_event("scene_displayed", {
        "sceneId": scene_id,
        "sceneName": scene.name
    })
    
    # Mock display functionality
    return {"message": f"Scene {scene_id} displayed successfully"}

# Overlays
@app.get("/api/overlays")
async def list_overlays(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    total = db.query(Overlay).count()
    overlays = db.query(Overlay).offset(offset).limit(limit).all()
    
    result = [
        OverlayResponse(
            id=o.id,
            name=o.name,
            description=o.description,
            channel=o.channel,
            pathRoot=o.path_root
        ) for o in overlays
    ]
    
    return {
        "overlays": result,
        "meta": PaginationMeta(total=total, limit=limit, offset=offset)
    }

# Display Management
@app.get("/api/display/status")
async def get_display_status(db: Session = Depends(get_db)):
    status = db.query(DisplayStatus).first()
    if not status:
        # Return default mock status
        return DisplayStatusResponse(
            hardware=DisplayHardware(
                type="mock",
                resolution=[800, 600],
                available=True
            ),
            currentScene=None,
            currentImage=None,
            resolution=[800, 600]
        )
    
    return DisplayStatusResponse(
        hardware=DisplayHardware(**status.hardware),
        currentScene=status.current_scene,
        currentImage=DisplayImage(**status.current_image) if status.current_image else None,
        resolution=status.resolution
    )

@app.post("/api/display/clear")
async def clear_display():
    # Broadcast display update event
    await broadcast_event("display_hardware_update", {
        "hardware": {
            "type": "mock",
            "available": True,
            "resolution": [800, 600]
        },
        "action": "display_cleared",
        "impact": {
            "currentScene": None,
            "displayActive": False
        }
    })
    
    return {"success": True}

# WebSocket status endpoint
@app.get("/api/websocket/status")
async def websocket_status():
    return {
        "connected_clients": len(manager.active_connections),
        "websocket_url": "ws://localhost:5000/ws",
        "current_sequence_id": manager.sequence_id,
        "features": {
            "full_state_on_connect": True,
            "heartbeat_support": True,
            "enhanced_events": True,
            "error_broadcasting": True,
            "channel_status_updates": True
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
