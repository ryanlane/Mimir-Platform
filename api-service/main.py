from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime
import json
import asyncio
import importlib.util
import sys
from pathlib import Path
import hashlib
import base64

# Database setup
DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
    pool_recycle=3600,
    pool_pre_ping=True
)
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
    # v2.1 additions
    schema_version = Column(String, default="2.1")
    permissions = Column(JSON, nullable=True)
    ui_config = Column(JSON, nullable=True)
    assets_config = Column(JSON, nullable=True)
    integrity_hashes = Column(JSON, nullable=True)
    channel_dir = Column(String, nullable=True)

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

# Channel Discovery and Management System
class ChannelDiscovery:
    def __init__(self, channels_dir: str = "channels"):
        self.channels_dir = Path(channels_dir)
        self.loaded_channels = {}
        self.static_mounts = {}
        
    def compute_sri_hash(self, file_path: Path) -> str:
        """Compute SHA-384 hash for Subresource Integrity"""
        if not file_path.exists():
            return ""
        
        hasher = hashlib.sha384()
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
        
        hash_bytes = hasher.digest()
        hash_b64 = base64.b64encode(hash_bytes).decode('ascii')
        return f"sha384-{hash_b64}"
    
    def load_channel_config(self, channel_path: Path) -> Optional[Dict[str, Any]]:
        """Load and validate channel config.json"""
        config_file = channel_path / "config.json"
        if not config_file.exists():
            return None
            
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            # Validate required fields
            required_fields = ['name', 'description', 'version']
            for field in required_fields:
                if field not in config:
                    print(f"Warning: Channel {channel_path.name} missing required field: {field}")
                    return None
                    
            # Set default schema version if not specified
            if 'schemaVersion' not in config:
                config['schemaVersion'] = '2.0'
                
            # Add computed integrity hashes for UI files
            if 'ui' in config:
                for ui_entry in config['ui']:
                    if 'moduleUrl' in ui_entry:
                        # Extract file path from URL
                        module_path = channel_path / "ui" / Path(ui_entry['moduleUrl']).name
                        if module_path.exists():
                            if 'integrity' not in ui_entry:
                                ui_entry['integrity'] = {}
                            ui_entry['integrity']['module'] = self.compute_sri_hash(module_path)
                    
                    if 'styleUrl' in ui_entry:
                        style_path = channel_path / "ui" / Path(ui_entry['styleUrl']).name  
                        if style_path.exists():
                            if 'integrity' not in ui_entry:
                                ui_entry['integrity'] = {}
                            ui_entry['integrity']['style'] = self.compute_sri_hash(style_path)
                            
            return config
            
        except json.JSONDecodeError as e:
            print(f"Error parsing config.json for {channel_path.name}: {e}")
            return None
        except Exception as e:
            print(f"Error loading channel {channel_path.name}: {e}")
            return None
    
    def load_channel_class(self, channel_path: Path) -> Optional[Any]:
        """Dynamically load channel implementation class"""
        channel_file = channel_path / "channel.py"
        if not channel_file.exists():
            return None
            
        try:
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"channel_{channel_path.name}", 
                channel_file
            )
            if spec is None or spec.loader is None:
                return None
                
            # Import the module
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"channel_{channel_path.name}"] = module
            spec.loader.exec_module(module)
            
            # Get the channel class
            if hasattr(module, 'ChannelClass'):
                ChannelClass = getattr(module, 'ChannelClass')
                return ChannelClass(str(channel_path))
            else:
                print(f"Warning: Channel {channel_path.name} has no ChannelClass export")
                return None
                
        except Exception as e:
            print(f"Error loading channel class for {channel_path.name}: {e}")
            return None
    
    def setup_static_mounts(self, app: FastAPI, channel_id: str, channel_path: Path):
        """Setup static file serving for channel UI and assets"""
        try:
            # Mount UI directory if it exists
            ui_path = channel_path / "ui"
            if ui_path.exists() and ui_path.is_dir():
                mount_path = f"/api/channels/{channel_id}/ui"
                app.mount(mount_path, StaticFiles(directory=str(ui_path)), name=f"{channel_id}-ui")
                self.static_mounts[f"{channel_id}-ui"] = mount_path
                print(f"Mounted UI static files: {mount_path} -> {ui_path}")
            
            # Mount assets directory if it exists  
            assets_path = channel_path / "assets"
            if assets_path.exists() and assets_path.is_dir():
                mount_path = f"/api/channels/{channel_id}/assets"
                app.mount(mount_path, StaticFiles(directory=str(assets_path)), name=f"{channel_id}-assets")
                self.static_mounts[f"{channel_id}-assets"] = mount_path
                print(f"Mounted assets static files: {mount_path} -> {assets_path}")
                
        except Exception as e:
            print(f"Error setting up static mounts for {channel_id}: {e}")
    
    def discover_channels(self, app: FastAPI) -> List[Dict[str, Any]]:
        """Discover and load all channels from filesystem"""
        if not self.channels_dir.exists():
            self.channels_dir.mkdir(exist_ok=True)
            print(f"Created channels directory: {self.channels_dir}")
            return []
        
        discovered_channels = []
        
        for channel_path in self.channels_dir.iterdir():
            if not channel_path.is_dir():
                continue
                
            channel_id = channel_path.name
            print(f"Discovering channel: {channel_id}")
            
            # Load configuration
            config = self.load_channel_config(channel_path)
            if not config:
                print(f"Skipping channel {channel_id}: invalid or missing config")
                continue
            
            # Load channel class
            channel_instance = self.load_channel_class(channel_path)
            
            # Setup static file serving
            self.setup_static_mounts(app, channel_id, channel_path)
            
            # Store loaded channel
            self.loaded_channels[channel_id] = {
                'config': config,
                'instance': channel_instance,
                'path': channel_path
            }
            
            # Add channel-specific routes if available
            if channel_instance and hasattr(channel_instance, 'get_router'):
                router = channel_instance.get_router()
                if router:
                    app.include_router(
                        router, 
                        prefix=f"/api/channels/{channel_id}",
                        tags=[f"Channel: {config.get('name', channel_id)}"]
                    )
                    print(f"Included router for channel: {channel_id}")
            
            discovered_channels.append({
                'id': channel_id,
                'config': config,
                'channel_dir': str(channel_path),
                'has_ui': 'ui' in config,
                'has_instance': channel_instance is not None
            })
            
            print(f"Successfully loaded channel: {channel_id}")
        
        print(f"Discovered {len(discovered_channels)} channels")
        return discovered_channels
    
    def get_manifest_for_ui(self) -> List[Dict[str, Any]]:
        """Get UI manifests for React plugin loader"""
        manifests = []
        
        for channel_id, channel_data in self.loaded_channels.items():
            config = channel_data['config']
            
            # Only include channels with UI configuration
            if 'ui' in config:
                manifest = {
                    'id': channel_id,
                    'name': config.get('name', channel_id),
                    'description': config.get('description', ''),
                    'version': config.get('version', '1.0.0'),
                    'schemaVersion': config.get('schemaVersion', '2.0'),
                    'permissions': config.get('permissions', []),
                    'ui': config['ui'],
                    'assets': config.get('assets', [])
                }
                manifests.append(manifest)
        
        return manifests
    
    def get_channel_instance(self, channel_id: str):
        """Get loaded channel instance by ID"""
        channel_data = self.loaded_channels.get(channel_id)
        return channel_data['instance'] if channel_data else None

# Global channel discovery instance
channel_discovery = ChannelDiscovery()

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

    async def send_full_state(self, websocket: WebSocket):
        """Send complete current state to a newly connected client"""
        db = SessionLocal()
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
        finally:
            db.close()

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
    # v2.1 additions
    schemaVersion: Optional[str] = "2.1"
    permissions: Optional[List[str]] = []
    hasUI: Optional[bool] = False
    hasAssets: Optional[bool] = False
    channelDir: Optional[str] = None

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

# Discover and load channels on startup
print("🔍 Discovering channels...")
discovered_channels = channel_discovery.discover_channels(app)
print(f"✅ Loaded {len(discovered_channels)} channels")

# Sync discovered channels with database
def sync_discovered_channels_to_db():
    """Update database with discovered filesystem channels"""
    db = SessionLocal()
    try:
        for channel_data in discovered_channels:
            channel_id = channel_data['id']
            config = channel_data['config']
            
            # Check if channel exists in database
            existing = db.query(Channel).filter(Channel.id == channel_id).first()
            
            if existing:
                # Update existing channel
                existing.name = config.get('name', channel_id)
                existing.description = config.get('description', '')
                existing.version = config.get('version', '1.0.0')
                existing.schema_version = config.get('schemaVersion', '2.1')
                existing.settings_type = config.get('settings_type', 'simple')
                existing.config_schema = config
                existing.permissions = config.get('permissions', [])
                existing.ui_config = config.get('ui', [])
                existing.assets_config = config.get('assets', [])
                existing.channel_dir = channel_data['channel_dir']
                print(f"📝 Updated channel in DB: {channel_id}")
            else:
                # Create new channel
                new_channel = Channel(
                    id=channel_id,
                    name=config.get('name', channel_id),
                    description=config.get('description', ''),
                    version=config.get('version', '1.0.0'),
                    schema_version=config.get('schemaVersion', '2.1'),
                    settings_type=config.get('settings_type', 'simple'),
                    config_schema=config,
                    permissions=config.get('permissions', []),
                    ui_config=config.get('ui', []),
                    assets_config=config.get('assets', []),
                    channel_dir=channel_data['channel_dir'],
                    current_settings={},
                    status={
                        "active": True,
                        "lastUpdate": datetime.datetime.now().isoformat(),
                        "lastError": None,
                        "usingFallback": False
                    }
                )
                db.add(new_channel)
                print(f"➕ Added new channel to DB: {channel_id}")
        
        db.commit()
        print("💾 Channel database sync completed")
    finally:
        db.close()

# Sync channels to database
sync_discovered_channels_to_db()

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        # Send full state snapshot on connection
        await manager.send_full_state(websocket)
        
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
                        await manager.send_full_state(websocket)
                        
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
            status=c.status,
            schemaVersion=c.schema_version,
            permissions=c.permissions or [],
            hasUI=bool(c.ui_config),
            hasAssets=bool(c.assets_config),
            channelDir=c.channel_dir
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

# v2.1 Channel Endpoints

@app.get("/api/channels/manifest")
async def get_channels_manifest():
    """Get UI-aware manifests for React plugin loader"""
    try:
        manifests = channel_discovery.get_manifest_for_ui()
        return manifests
    except Exception as e:
        print(f"Error getting channel manifests: {e}")
        raise HTTPException(status_code=500, detail="Failed to load channel manifests")

@app.post("/api/channels/{channel_id}/test")
async def test_channel(channel_id: str):
    """Test channel functionality"""
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=404, detail="Channel not found or not loaded")
    
    try:
        # Test basic channel functions
        status = channel_instance.get_status()
        config = channel_instance.config
        
        # If channel has a test method, call it
        if hasattr(channel_instance, 'test'):
            test_result = await channel_instance.test()
        else:
            test_result = {"message": "Channel loaded successfully", "basic_test": True}
        
        return {
            "success": True,
            "channelId": channel_id,
            "status": status,
            "test_result": test_result,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "channelId": channel_id,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }

@app.get("/api/channels/{channel_id}/health")
async def get_channel_health(channel_id: str):
    """Get channel health status"""
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    try:
        status = channel_instance.get_status()
        config = channel_instance.config
        
        health = {
            "channelId": channel_id,
            "name": config.get("name", channel_id),
            "version": config.get("version", "unknown"),
            "status": status,
            "healthy": status.get("active", False) and not status.get("lastError"),
            "lastCheck": datetime.datetime.now().isoformat()
        }
        
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/api/channels/{channel_id}/token")
async def get_channel_token(channel_id: str):
    """Get channel-scoped authentication token"""
    # TODO: Implement proper JWT token generation with channel scopes
    # For now, return a mock token
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    config = channel_instance.config
    permissions = config.get("permissions", [])
    
    # Mock token - in production, generate proper JWT
    mock_token = f"channel_{channel_id}_{int(datetime.datetime.now().timestamp())}"
    
    return {
        "token": mock_token,
        "channelId": channel_id,
        "permissions": permissions,
        "expiresIn": 3600,  # 1 hour
        "tokenType": "Bearer"
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
