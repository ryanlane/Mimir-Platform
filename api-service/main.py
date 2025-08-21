from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base
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
import uuid
from time import time
from collections import defaultdict

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
    orientation = Column(String, default="landscape")  # "landscape", "portrait"
    refresh_rate_hz = Column(Integer, nullable=True)  # Display refresh rate
    client_version = Column(String, nullable=True)  # Client software version
    
    # Connection status
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    last_image_fetch = Column(DateTime, nullable=True)  # When client last fetched image
    websocket_connection_id = Column(String, nullable=True)
    
    # Current assignment
    assigned_scene_id = Column(String, nullable=True)  # ForeignKey to scenes
    current_image_path = Column(String, nullable=True)  # Path to current scene image
    
    # Configuration
    settings = Column(JSON, nullable=True)  # Display-specific settings
    tags = Column(JSON, nullable=True)  # ["lobby", "conference-room", "kiosk"]
    
    # Metadata
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

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

# WebSocket Connection Manager with Multi-Display Support
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.display_connections: Dict[str, WebSocket] = {}  # display_client_id -> websocket
        self.connection_metadata: Dict[WebSocket, Dict] = {}  # websocket -> metadata
        self.sequence_id = 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {"type": "dashboard", "connected_at": datetime.datetime.now()}

    async def connect_display_client(self, websocket: WebSocket, display_client_id: str):
        """Connect a specific display client"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.display_connections[display_client_id] = websocket
        self.connection_metadata[websocket] = {
            "type": "display", 
            "display_id": display_client_id,
            "connected_at": datetime.datetime.now()
        }
        
        # Update database status
        db = SessionLocal()
        try:
            client = db.query(DisplayClient).filter(DisplayClient.id == display_client_id).first()
            if client:
                client.is_online = True
                client.last_seen = datetime.datetime.now()
                db.commit()
        finally:
            db.close()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        # Handle display client disconnection
        metadata = self.connection_metadata.get(websocket, {})
        if metadata.get("type") == "display":
            display_id = metadata.get("display_id")
            if display_id and display_id in self.display_connections:
                del self.display_connections[display_id]
                
                # Update database status
                db = SessionLocal()
                try:
                    client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
                    if client:
                        client.is_online = False
                        db.commit()
                finally:
                    db.close()
        
        # Clean up metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]

    def get_next_sequence_id(self) -> int:
        self.sequence_id += 1
        return self.sequence_id

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def send_to_display_client(self, display_client_id: str, message: dict):
        """Send message to specific display client"""
        websocket = self.display_connections.get(display_client_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps(message))
                return True
            except:
                self.disconnect(websocket)
                return False
        return False

    async def broadcast_to_display_clients(self, message: dict, target_display_ids: Optional[List[str]] = None):
        """Broadcast to display clients (all or specific ones)"""
        message_str = json.dumps(message)
        results = {}
        
        target_connections = {}
        if target_display_ids:
            # Send to specific display clients
            for display_id in target_display_ids:
                if display_id in self.display_connections:
                    target_connections[display_id] = self.display_connections[display_id]
        else:
            # Send to all display clients
            target_connections = self.display_connections.copy()
        
        for display_id, websocket in target_connections.items():
            try:
                await websocket.send_text(message_str)
                results[display_id] = True
            except:
                self.disconnect(websocket)
                results[display_id] = False
                
        return results

    async def broadcast_to_dashboard_clients(self, message: dict):
        """Broadcast to dashboard/admin clients only"""
        message_str = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            metadata = self.connection_metadata.get(connection, {})
            if metadata.get("type") != "display":  # Send to non-display clients
                try:
                    await connection.send_text(message_str)
                except:
                    disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

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

# Multi-Display Client Models
class DisplayClientCapabilities(BaseModel):
    resolution: List[int]  # [width, height]
    supported_formats: List[str]  # ["jpg", "png", "gif"]
    orientation: str = "landscape"  # "landscape" | "portrait"
    refresh_rate_hz: Optional[int] = 60  # Display refresh rate

class DisplayClientRegistration(BaseModel):
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    capabilities: DisplayClientCapabilities
    tags: Optional[List[str]] = None
    client_version: Optional[str] = "1.0.0"  # Client software version

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
    last_seen: Optional[str]
    assigned_scene_id: Optional[str]
    assigned_scene_name: Optional[str]
    resolution: Optional[List[int]]
    orientation: str
    refresh_rate_hz: Optional[int]
    tags: Optional[List[str]]
    client_version: Optional[str]
    current_image_url: Optional[str]  # URL to fetch latest image

class SceneAssignment(BaseModel):
    scene_id: Optional[str]  # None to unassign

# Initialize FastAPI app
app = FastAPI(title="Mimir Platform API", version="1.0")

# Global rate limiting configuration
GLOBAL_RATE_LIMITS = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 120  # Max 120 requests per minute per IP (2 per second average)

# Rate limiting dependency
async def check_rate_limit(request: Request):
    """Dependency to check rate limits for all endpoints"""
    client_ip = request.client.host if request.client else "unknown"
    current_time = time()
    path = request.url.path
    
    # Periodic cleanup (every 100th request roughly)
    if len(GLOBAL_RATE_LIMITS) > 20 and int(current_time) % 100 == 0:
        cleanup_rate_limit_data()
    
    # Skip rate limiting for static files and health checks
    if (path.startswith("/api/channels/") and "/ui/" in path) or \
       (path.startswith("/api/channels/") and "/assets/" in path) or \
       path == "/":
        return True
    
    # Get client's request history
    client_requests = GLOBAL_RATE_LIMITS[client_ip]
    
    # Remove old requests outside the window
    client_requests[:] = [req_time for req_time in client_requests 
                         if current_time - req_time < RATE_LIMIT_WINDOW]
    
    # Check if client has exceeded rate limit
    if len(client_requests) >= RATE_LIMIT_MAX_REQUESTS:
        retry_after = int(RATE_LIMIT_WINDOW - (current_time - client_requests[0]))
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Too many requests from {client_ip}",
                "limit": RATE_LIMIT_MAX_REQUESTS,
                "window_seconds": RATE_LIMIT_WINDOW,
                "retry_after": retry_after,
                "current_requests": len(client_requests),
                "suggestion": "Please reduce request frequency or implement client-side caching",
                "endpoint": path
            }
        )
    
    # Add current request to history
    client_requests.append(current_time)
    return True

# Global rate limit enforcement function
def add_global_rate_limiting():
    """Add rate limiting to all API endpoints after they're defined"""
    api_routes = [route for route in app.routes if hasattr(route, 'path') and route.path.startswith('/api/')]
    rate_limited_count = 0
    
    for route in api_routes:
        # Skip static file routes and already rate limited routes
        if ('/ui/' in route.path or '/assets/' in route.path or 
            hasattr(route, '_rate_limited')):
            continue
            
        # Add rate limiting dependency to route
        if hasattr(route, 'dependant') and route.dependant:
            # Mark as rate limited to avoid double-processing
            route._rate_limited = True
            rate_limited_count += 1
    
    print(f"🛡️  Applied global rate limiting to {rate_limited_count} API endpoints")
    print(f"📊 Rate limit: {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds per IP")

# Cleanup function for rate limit data
def cleanup_rate_limit_data():
    """Clean up old rate limit entries to prevent memory leaks"""
    current_time = time()
    clients_to_remove = []
    
    for client_ip, requests in GLOBAL_RATE_LIMITS.items():
        # Remove old requests
        requests[:] = [req_time for req_time in requests 
                      if current_time - req_time < RATE_LIMIT_WINDOW]
        # Mark empty clients for removal
        if not requests:
            clients_to_remove.append(client_ip)
    
    # Remove empty clients
    for client_ip in clients_to_remove:
        del GLOBAL_RATE_LIMITS[client_ip]

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

# Note: Background cleanup will be handled during normal rate limit checks

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
    db: Session = Depends(get_db),
    _rate_limit: bool = Depends(check_rate_limit)
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
async def get_channel_config(channel_id: str, db: Session = Depends(get_db), _: dict = Depends(check_rate_limit)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return channel.config_schema or {}

@app.get("/api/channels/{channel_id}/settings")
async def get_channel_settings(channel_id: str, db: Session = Depends(get_db), _: dict = Depends(check_rate_limit)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    # Load channel config from filesystem
    channel_path = Path("channels") / channel_id / "config.json"
    if not channel_path.exists():
        raise HTTPException(status_code=404, detail="Channel config not found")
    import json
    with open(channel_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    settings = config.get("settings", {})

    # Defaults
    default_unit = "minutes"
    default_value = 30
    unit_enum = ["days", "hours", "minutes", "seconds"]

    # Get update_interval_unit
    unit_setting = settings.get("update_interval_unit", {})
    active_unit = unit_setting.get("default", default_unit)
    enum = unit_setting.get("enum", unit_enum)
    unit_label = unit_setting.get("label", "Update Interval Unit")

    # Get update_interval_value
    value_setting = settings.get("update_interval_value", {})
    active_value = value_setting.get("default", default_value)
    value_label = value_setting.get("label", "Update Interval Value")
    minimum = value_setting.get("minimum", 1)

    # Compose settings response
    response = {
        "update_interval_unit": {
            "type": "string",
            "enum": enum,
            "label": unit_label,
            "default": default_unit,
            "value": active_unit
        },
        "update_interval_value": {
            "type": "integer",
            "minimum": minimum,
            "label": value_label,
            "default": default_value,
            "value": active_value
        }
    }
    # Add any other settings from config
    for k, v in settings.items():
        if k not in response:
            response[k] = v
    return response
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
    # Get channel instance
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")

    # Call render_image
    try:
        image_path = await channel_instance.render_image(
            resolution=tuple(request_body.resolution),
            orientation=request_body.orientation,
            settings={}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

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

    return {
        "success": True,
        "image_path": image_path,
        "message": "Image generated successfully"
    }

# v2.1 Channel Endpoints

# Cache for channel manifest to prevent excessive computation
_manifest_cache = {
    "data": None,
    "timestamp": 0,
    "cache_duration": 10  # Cache for 10 seconds (manifest changes rarely)
}

# Rate limiting for manifest endpoint
_manifest_rate_limits = defaultdict(list)
_manifest_rate_limit_window = 60  # 1 minute window  
_manifest_max_requests_per_window = 100  # Max 100 requests per minute per IP (secondary limit after global)

@app.get("/api/channels/manifest")
async def get_channels_manifest(request: Request, response: Response):
    """Get UI-aware manifests for React plugin loader with caching and rate limiting"""
    current_time = time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limiting check
    client_requests = _manifest_rate_limits[client_ip]
    # Remove old requests outside the window
    client_requests[:] = [req_time for req_time in client_requests 
                         if current_time - req_time < _manifest_rate_limit_window]
    
    if len(client_requests) >= _manifest_max_requests_per_window:
        raise HTTPException(
            status_code=429, 
            detail={
                "error": "Rate limit exceeded for channels manifest endpoint",
                "limit": _manifest_max_requests_per_window,
                "window_seconds": _manifest_rate_limit_window,
                "retry_after": int(_manifest_rate_limit_window - (current_time - client_requests[0])),
                "suggestion": "Cache this response locally for 10+ seconds to reduce requests"
            }
        )
    
    # Add current request to rate limit tracking
    client_requests.append(current_time)
    
    # Check if we have fresh cached data
    if (_manifest_cache["data"] and 
        current_time - _manifest_cache["timestamp"] < _manifest_cache["cache_duration"]):
        # For cached responses, add rate limit info as custom headers
        response.headers["X-Cache-Status"] = "HIT"
        response.headers["X-Cache-Age"] = str(int(current_time - _manifest_cache["timestamp"]))
        response.headers["X-Rate-Limit-Remaining"] = str(_manifest_max_requests_per_window - len(client_requests))
        response.headers["X-Rate-Limit-Reset"] = str(int(current_time + _manifest_rate_limit_window))
        response.headers["Cache-Control"] = f"public, max-age={_manifest_cache['cache_duration']}"
        cached_data = _manifest_cache["data"]
        return cached_data
    
    try:
        # Generate fresh manifest data
        manifests = channel_discovery.get_manifest_for_ui()
        
        # Add headers for fresh responses
        response.headers["X-Cache-Status"] = "MISS"
        response.headers["X-Cache-Age"] = "0"
        response.headers["X-Rate-Limit-Remaining"] = str(_manifest_max_requests_per_window - len(client_requests))
        response.headers["X-Rate-Limit-Reset"] = str(int(current_time + _manifest_rate_limit_window))
        response.headers["Cache-Control"] = f"public, max-age={_manifest_cache['cache_duration']}"
        
        # Update cache (store the raw array)
        _manifest_cache["data"] = manifests
        _manifest_cache["timestamp"] = current_time
        
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

# Channels
@app.get("/api/channels/{channel_id}/status")
async def get_channel_status(channel_id: str, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    status = channel.status or {
        "active": True,
        "lastUpdate": None,
        "lastError": None,
        "usingFallback": False
    }
    return {
        "id": channel.id,
        "name": channel.name,
        "version": channel.version,
        "status": status
    }

# Scenes
@app.get("/api/scenes")
async def list_scenes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _rate_limit: bool = Depends(check_rate_limit)
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
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
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
async def get_display_status(db: Session = Depends(get_db), _: dict = Depends(check_rate_limit)):
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

# WebSocket status endpoint with caching and rate limiting
from time import time
from collections import defaultdict

# Cache for WebSocket status to prevent excessive computation
_websocket_status_cache = {
    "data": None,
    "timestamp": 0,
    "cache_duration": 5  # Cache for 5 seconds
}

# Rate limiting for WebSocket status endpoint
_status_rate_limits = defaultdict(list)
_rate_limit_window = 60  # 1 minute window
_max_requests_per_window = 50  # Max 50 requests per minute per IP (secondary limit after global)

def cleanup_rate_limits():
    """Clean up old rate limit entries to prevent memory leaks"""
    current_time = time()
    clients_to_remove = []
    
    for client_ip, requests in _status_rate_limits.items():
        # Remove old requests
        requests[:] = [req_time for req_time in requests 
                      if current_time - req_time < _rate_limit_window]
        # Mark empty clients for removal
        if not requests:
            clients_to_remove.append(client_ip)
    
    # Remove empty clients
    for client_ip in clients_to_remove:
        del _status_rate_limits[client_ip]

@app.get("/api/websocket/status")
async def websocket_status(request: Request):
    current_time = time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Periodic cleanup of rate limits (every 100th request roughly)
    if len(_status_rate_limits) > 50:  # Only cleanup when we have many entries
        cleanup_rate_limits()
    
    # Rate limiting check
    client_requests = _status_rate_limits[client_ip]
    # Remove old requests outside the window
    client_requests[:] = [req_time for req_time in client_requests 
                         if current_time - req_time < _rate_limit_window]
    
    if len(client_requests) >= _max_requests_per_window:
        raise HTTPException(
            status_code=429, 
            detail={
                "error": "Rate limit exceeded for WebSocket status endpoint",
                "limit": _max_requests_per_window,
                "window_seconds": _rate_limit_window,
                "retry_after": int(_rate_limit_window - (current_time - client_requests[0])),
                "suggestion": "Consider caching the status locally or reducing polling frequency"
            }
        )
    
    # Add current request to rate limit tracking
    client_requests.append(current_time)
    
    # Check if we have fresh cached data
    if (_websocket_status_cache["data"] and 
        current_time - _websocket_status_cache["timestamp"] < _websocket_status_cache["cache_duration"]):
        cached_data = _websocket_status_cache["data"].copy()
        cached_data["cache_info"]["served_from_cache"] = True
        cached_data["rate_limit_info"] = {
            "requests_in_window": len(client_requests),
            "max_requests": _max_requests_per_window,
            "window_seconds": _rate_limit_window
        }
        return cached_data
    
    # Generate fresh status data
    status_data = {
        "connected_clients": len(manager.active_connections),
        "websocket_url": "ws://localhost:5000/ws",
        "current_sequence_id": manager.sequence_id,
        "features": {
            "full_state_on_connect": True,
            "heartbeat_support": True,
            "enhanced_events": True,
            "error_broadcasting": True,
            "channel_status_updates": True
        },
        "cache_info": {
            "cached_at": current_time,
            "cache_duration_seconds": _websocket_status_cache["cache_duration"],
            "served_from_cache": False
        },
        "rate_limit_info": {
            "requests_in_window": len(client_requests),
            "max_requests": _max_requests_per_window,
            "window_seconds": _rate_limit_window
        },
        "optimization_suggestions": {
            "polling_frequency": "Consider polling every 10-30 seconds instead of continuously",
            "caching": "Cache this response locally for the duration specified in cache_info",
            "websocket_alternative": "Use WebSocket connection for real-time updates instead of polling"
        }
    }
    
    # Update cache
    _websocket_status_cache["data"] = status_data
    _websocket_status_cache["timestamp"] = current_time
    
    return status_data

# =============================================================================
# MULTI-DISPLAY CLIENT ENDPOINTS
# =============================================================================

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
        orientation=registration.capabilities.orientation,
        refresh_rate_hz=registration.capabilities.refresh_rate_hz,
        client_version=registration.client_version,
        tags=registration.tags,
        is_online=False,
        created_at=datetime.datetime.now()
    )
    
    db.add(display_client)
    db.commit()
    db.refresh(display_client)
    
    # Broadcast new display registration
    await broadcast_event("display_client_registered", {
        "displayId": display_id,
        "name": registration.name,
        "location": registration.location,
        "capabilities": registration.capabilities.model_dump()
    })
    
    return DisplayClientResponse(
        id=display_client.id,
        name=display_client.name,
        description=display_client.description,
        location=display_client.location,
        is_online=display_client.is_online,
        last_seen=display_client.last_seen.isoformat() if display_client.last_seen else None,
        assigned_scene_id=display_client.assigned_scene_id,
        assigned_scene_name=None,
        resolution=display_client.resolution,
        orientation=display_client.orientation,
        refresh_rate_hz=display_client.refresh_rate_hz,
        tags=display_client.tags,
        client_version=display_client.client_version,
        current_image_url=None
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
    
    if tag and tag.strip():
        # Simple tag filtering - check if tag exists in the tags JSON array
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
            last_seen=client.last_seen.isoformat() if client.last_seen else None,
            assigned_scene_id=client.assigned_scene_id,
            assigned_scene_name=scene_names.get(client.assigned_scene_id),
            resolution=client.resolution,
            orientation=client.orientation,
            refresh_rate_hz=client.refresh_rate_hz,
            tags=client.tags,
            client_version=client.client_version,
            current_image_url=f"/api/displays/{client.id}/current_image" if client.assigned_scene_id else None
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
    display_client.updated_at = datetime.datetime.now()
    db.commit()
    
    # Send targeted WebSocket message to the specific display
    scene_assignment_message = {
        "event": "scene_assigned",
        "data": {
            "displayId": display_id,
            "sceneId": assignment.scene_id,
            "sceneName": scene.name if scene else None,
            "previousSceneId": old_scene_id,
            "timestamp": datetime.datetime.now().isoformat()
        },
        "timestamp": datetime.datetime.now().isoformat(),
        "sequenceId": manager.get_next_sequence_id()
    }
    
    # Send to specific display client
    sent = await manager.send_to_display_client(display_id, scene_assignment_message)
    
    # Also broadcast to dashboard clients for monitoring
    await manager.broadcast_to_dashboard_clients({
        "event": "display_assignment_updated",
        "data": {
            "displayId": display_id,
            "displayName": display_client.name,
            "newSceneId": assignment.scene_id,
            "newSceneName": scene.name if scene else None,
            "previousSceneId": old_scene_id
        },
        "timestamp": datetime.datetime.now().isoformat()
    })
    
    return {
        "message": f"Scene assignment updated for display {display_client.name}",
        "assigned_scene": scene.name if scene else None,
        "message_sent": sent
    }

@app.delete("/api/displays/{display_id}/assign_scene")
async def unassign_scene_from_display(
    display_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Remove scene assignment from a display client"""
    
    # Get display client
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Store previous assignment for messaging
    old_scene_id = display_client.assigned_scene_id
    old_scene_name = None
    if old_scene_id:
        old_scene = db.query(Scene).filter(Scene.id == old_scene_id).first()
        if old_scene:
            old_scene_name = old_scene.name
    
    # Remove assignment
    display_client.assigned_scene_id = None
    display_client.updated_at = datetime.datetime.now()
    db.commit()
    
    # Send targeted WebSocket message to the specific display
    scene_unassignment_message = {
        "event": "scene_unassigned",
        "data": {
            "displayId": display_id,
            "previousSceneId": old_scene_id,
            "previousSceneName": old_scene_name,
            "timestamp": datetime.datetime.now().isoformat()
        },
        "timestamp": datetime.datetime.now().isoformat(),
        "sequenceId": manager.get_next_sequence_id()
    }
    
    # Send to specific display client
    sent = await manager.send_to_display_client(display_id, scene_unassignment_message)
    
    # Also broadcast to dashboard clients for monitoring
    await manager.broadcast_to_dashboard_clients({
        "event": "display_assignment_updated",
        "data": {
            "displayId": display_id,
            "displayName": display_client.name,
            "newSceneId": None,
            "newSceneName": None,
            "previousSceneId": old_scene_id,
            "previousSceneName": old_scene_name
        },
        "timestamp": datetime.datetime.now().isoformat()
    })
    
    return {
        "message": f"Scene unassigned from display {display_client.name}",
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
    
    # Connect the display client
    await manager.connect_display_client(websocket, display_id)
    
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
                        "timestamp": datetime.datetime.now().isoformat()
                    }))
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_text(json.dumps({
                    "event": "ping",
                    "data": {"timestamp": datetime.datetime.now().isoformat()},
                    "timestamp": datetime.datetime.now().isoformat()
                }))
                
    except Exception as e:
        print(f"Display WebSocket error for {display_id}: {e}")
    finally:
        manager.disconnect(websocket)

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
                "serverTime": datetime.datetime.now().isoformat()
            },
            "timestamp": datetime.datetime.now().isoformat()
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
            "data": {"timestamp": datetime.datetime.now().isoformat()},
            "timestamp": datetime.datetime.now().isoformat()
        }))
        
    elif event_type == "display_status_update":
        # Update display status
        data = message.get("data", {})
        
        # Broadcast status update to dashboard clients
        await manager.broadcast_to_dashboard_clients({
            "event": "display_status_updated",
            "data": {
                "displayId": display_id,
                "status": data,
                "timestamp": datetime.datetime.now().isoformat()
            },
            "timestamp": datetime.datetime.now().isoformat()
        })
        
    elif event_type == "request_scene_refresh":
        # Display client requesting scene refresh
        await send_display_initial_state(websocket, display_id)

@app.post("/api/scenes/{scene_id}/activate_on_displays")
async def activate_scene_on_displays(
    scene_id: str,
    display_ids: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Activate a scene on specific display clients or all assigned displays"""
    
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # If no display IDs specified, get all displays assigned to this scene
    if display_ids is None:
        assigned_displays = db.query(DisplayClient).filter(
            DisplayClient.assigned_scene_id == scene_id,
            DisplayClient.is_online == True
        ).all()
        display_ids = [d.id for d in assigned_displays]
    
    # Send activation message to target displays
    activation_message = {
        "event": "scene_activated",
        "data": {
            "sceneId": scene_id,
            "sceneName": scene.name,
            "channels": scene.channels or [],
            "overlay": scene.overlay,
            "timestamp": datetime.datetime.now().isoformat()
        },
        "timestamp": datetime.datetime.now().isoformat(),
        "sequenceId": manager.get_next_sequence_id()
    }
    
    results = await manager.broadcast_to_display_clients(activation_message, display_ids)
    
    return {
        "message": f"Scene {scene.name} activated on {len(display_ids)} displays",
        "target_displays": display_ids,
        "delivery_results": results
    }

@app.get("/api/displays/{display_id}/current_image")
async def get_display_current_image(
    display_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Get the current scene image for a specific display client"""
    
    # Get display client
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Update last image fetch time
    display_client.last_image_fetch = datetime.datetime.now()
    display_client.last_seen = datetime.datetime.now()
    db.commit()
    
    # Check if display has assigned scene
    if not display_client.assigned_scene_id:
        raise HTTPException(status_code=404, detail="No scene assigned to this display")
    
    # Get assigned scene
    scene = db.query(Scene).filter(Scene.id == display_client.assigned_scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Assigned scene not found")
    
    # Generate/get scene image based on display capabilities
    try:
        image_info = await generate_scene_image_for_display(scene, display_client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    return {
        "display_id": display_id,
        "scene_id": scene.id,
        "scene_name": scene.name,
        "image_url": image_info["url"],
        "image_path": image_info["path"],
        "resolution": image_info["resolution"],
        "generated_at": image_info["generated_at"],
        "channels": image_info["channels_rendered"],
        "cache_expires_in": image_info["cache_expires_in"]
    }

@app.get("/api/displays/{display_id}/current_image_file")
async def get_display_current_image_file(
    display_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Download the actual image file for the display client"""
    
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    if not display_client.assigned_scene_id:
        raise HTTPException(
            status_code=404, 
            detail="No scene assigned to this display",
            headers={
                "X-Display-ID": display_id,
                "X-Display-Name": display_client.name
            }
        )
    
    # Get the scene
    scene = db.query(Scene).filter(Scene.id == display_client.assigned_scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Assigned scene not found")
    
    try:
        image_info = await generate_scene_image_for_display(scene, display_client)
        image_file_path = Path(image_info["path"])
        if not image_file_path.exists():
            raise HTTPException(status_code=404, detail=f"Image file not found: {image_file_path}")
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(image_file_path),
            media_type="image/jpeg",
            headers={
                "Last-Modified": image_info["generated_at"],
                "Cache-Control": f"max-age={image_info.get('cache_expires_in', 300)}",
                "X-Display-ID": display_id,
                "X-Scene-ID": scene.id
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve display image: {str(e)}")

@app.get("/api/displays/{display_id}/status")
async def get_display_status(
    display_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Get detailed status information for a display client"""
    
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")

    # Get assigned scene info
    assigned_scene = None
    poll_interval = 60  # default to 60 seconds
    if display_client.assigned_scene_id:
        assigned_scene = db.query(Scene).filter(Scene.id == display_client.assigned_scene_id).first()
        # Get first channel in the scene
        if assigned_scene and assigned_scene.channels:
            channel_id = assigned_scene.channels[0]
            # Load channel config from filesystem
            channel_config_path = Path("channels") / channel_id / "config.json"
            if channel_config_path.exists():
                import json
                with open(channel_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                settings = config.get("settings", {})
                unit_setting = settings.get("update_interval_unit", {})
                value_setting = settings.get("update_interval_value", {})
                unit = unit_setting.get("value", unit_setting.get("default", "minutes"))
                value = value_setting.get("value", value_setting.get("default", 30))
                unit = str(unit).strip().lower()
                multipliers = {
                    'seconds': 1,
                    'minutes': 60,
                    'hours': 3600,
                    'days': 86400
                }
                poll_interval = int(value) * multipliers.get(unit, 60)

    return {
        "display_id": display_client.id,
        "name": display_client.name,
        "location": display_client.location,
        "is_online": display_client.is_online,
        "last_seen": display_client.last_seen.isoformat() if display_client.last_seen else None,
        "assigned_scene_id": display_client.assigned_scene_id,
        "assigned_scene_name": assigned_scene.name if assigned_scene else None,
        "resolution": display_client.resolution,
        "orientation": display_client.orientation,
        "refresh_rate_hz": display_client.refresh_rate_hz,
        "tags": display_client.tags,
        "client_version": display_client.client_version,
        "current_image_url": f"/api/displays/{display_client.id}/current_image" if display_client.assigned_scene_id else None,
        "poll_interval": poll_interval
    }

@app.put("/api/displays/{display_id}")
async def update_display_client(
    display_id: str,
    update_data: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Update display client information and settings"""
    
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Update allowed fields
    if "name" in update_data:
        display_client.name = update_data["name"]
    if "description" in update_data:
        display_client.description = update_data["description"]
    if "location" in update_data:
        display_client.location = update_data["location"]
    if "tags" in update_data:
        display_client.tags = update_data["tags"]
    if "settings" in update_data:
        display_client.settings = update_data["settings"]
    
    try:
        db.commit()
        
        # Broadcast update event
        await broadcast_event("display_client_updated", {
            "displayId": display_id,
            "displayName": display_client.name,
            "location": display_client.location,
            "tags": display_client.tags,
            "triggeredBy": {
                "source": "api",
                "timestamp": datetime.datetime.now().isoformat()
            }
        })
        
        return {
            "message": "Display client updated successfully",
            "display_id": display_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update display client: {str(e)}")

@app.delete("/api/displays/{display_id}")
async def delete_display_client(
    display_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Remove a display client from the system"""
    
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    display_name = display_client.name
    
    try:
        # Remove the display client from database
        db.delete(display_client)
        db.commit()
        
        # Broadcast deletion event
        await broadcast_event("display_client_deleted", {
            "displayId": display_id,
            "displayName": display_name,
            "triggeredBy": {
                "source": "api",
                "timestamp": datetime.datetime.now().isoformat()
            }
        })
        
        return {
            "message": f"Display client {display_name} deleted successfully"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete display client: {str(e)}")

async def generate_scene_image_for_display(scene, display_client):
    """Generate scene image optimized for specific display client"""
    
    # Get display resolution and orientation
    resolution = display_client.resolution or [1920, 1080]
    orientation = display_client.orientation or "landscape"

    # For this implementation, use the example_channel's generated image
    # Assume the first channel in the scene is the one to use
    channel_id = scene.channels[0] if scene.channels else "example_channel"
    image_url = f"/api/channels/{channel_id}/assets/current.jpg"
    image_path = f"channels/{channel_id}/assets/current.jpg"

    image_info = {
        "url": image_url,
        "path": image_path,
        "resolution": resolution,
        "generated_at": datetime.datetime.now().isoformat(),
        "cache_expires_in": 300,
        "channels_rendered": scene.channels or [],
        "orientation": orientation
    }

    # Update display client's current image path
    db = SessionLocal()
    try:
        display_client.current_image_path = image_path
        db.commit()
    finally:
        db.close()

    return image_info
