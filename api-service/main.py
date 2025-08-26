from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime
import json
import asyncio
import importlib.util
import sys
import os
import logging
from pathlib import Path
import hashlib
import base64
import uuid
from time import time
from collections import defaultdict
from enum import Enum

# Setup logging
logger = logging.getLogger(__name__)

# Redis integration
try:
    from redis_manager import get_redis_manager, init_redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Distribution Mode Enum
class DistributionMode(str, Enum):
    """Content distribution modes for multi-display systems"""
    MIRROR = "MIRROR"                    # All displays show the same content (default)
    SEQUENTIAL = "SEQUENTIAL"            # Displays cycle through content in order
    RANDOM_UNIQUE = "RANDOM_UNIQUE"      # Displays get randomized content without duplication

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
    # Redis integration: distribution mode
    distribution_mode = Column(String, default=DistributionMode.MIRROR.value)
    # Content versioning for Redis integration
    content_hash = Column(String, nullable=True)
    content_epoch = Column(String, nullable=True)

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

# Redis Integration: Distribution Queue for SQL Fallback
class DistributionQueue(Base):
    """SQL fallback table for content distribution when Redis is unavailable"""
    __tablename__ = "distribution_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(String, index=True)
    content_id = Column(String)  # Content item identifier
    queue_position = Column(Integer)  # Position in queue for sequential mode
    
    # Claim tracking
    claimed_at = Column(DateTime, nullable=True)
    claimed_by = Column(String, nullable=True)  # Display ID that claimed this content
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now)
    epoch_id = Column(String, nullable=True)  # Content epoch for tracking updates

# Redis Integration: Content Leases Audit Table
class ContentLease(Base):
    """Audit table for tracking content assignments and leases"""
    __tablename__ = "content_leases"
    
    id = Column(Integer, primary_key=True, index=True)
    lease_id = Column(String, unique=True, index=True)  # Redis lease key
    scene_id = Column(String, index=True)
    display_id = Column(String, index=True)
    content_id = Column(String)
    
    # Lease lifecycle
    assigned_at = Column(DateTime, default=datetime.datetime.now)
    acknowledged_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime)
    
    # Status tracking
    status = Column(String, default="assigned")  # assigned, acknowledged, expired, released
    distribution_mode = Column(String)
    assignment_id = Column(String, nullable=True)  # Client-side assignment tracking

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
            print(f"⚠️  No channel.py found for {channel_path.name}")
            return None
            
        try:
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"channel_{channel_path.name}", 
                channel_file
            )
            if spec is None or spec.loader is None:
                print(f"❌ Failed to create module spec for {channel_path.name}")
                return None
                
            # Import the module
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"channel_{channel_path.name}"] = module
            spec.loader.exec_module(module)
            
            # Look for channel class in multiple ways
            channel_class = None
            
            # 1. Look for ChannelClass export (preferred)
            if hasattr(module, 'ChannelClass'):
                channel_class = getattr(module, 'ChannelClass')
                print(f"✅ Found ChannelClass in {channel_path.name}")
                
            # 2. Look for class with "Channel" in the name
            elif hasattr(module, f'{channel_path.name.title().replace("_", "")}Channel'):
                class_name = f'{channel_path.name.title().replace("_", "")}Channel'
                channel_class = getattr(module, class_name)
                print(f"✅ Found {class_name} in {channel_path.name}")
                
            # 3. Look for any class ending with "Channel"
            else:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        attr_name.endswith('Channel') and 
                        attr.__module__ == module.__name__):
                        channel_class = attr
                        print(f"✅ Found channel class {attr_name} in {channel_path.name}")
                        break
            
            if channel_class:
                try:
                    return channel_class(str(channel_path))
                except Exception as e:
                    print(f"❌ Failed to instantiate channel class for {channel_path.name}: {e}")
                    return None
            else:
                print(f"❌ No suitable channel class found in {channel_path.name}")
                # List available classes for debugging
                classes = [name for name in dir(module) 
                          if isinstance(getattr(module, name), type) 
                          and getattr(module, name).__module__ == module.__name__]
                print(f"   Available classes: {classes}")
                return None
                
        except Exception as e:
            print(f"❌ Error loading channel class for {channel_path.name}: {e}")
            import traceback
            traceback.print_exc()
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
                
            # First attempt to load config to get the ID
            config = self.load_channel_config(channel_path)
            if not config:
                print(f"Skipping channel {channel_path.name}: invalid or missing config")
                continue
                
            # Use ID from config if present, otherwise fall back to directory name
            # This allows channels to specify their canonical ID in config.json
            # If ID changes, the channel will be re-registered with the new ID
            channel_id = config.get('id', channel_path.name)
            print(f"Discovering channel: {channel_id} (directory: {channel_path.name})")
            
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

    # Redis-Powered Distribution Event Methods
    async def broadcast_content_assigned(self, content_id: str, display_client_id: str, lease_data: dict):
        """Broadcast when content is assigned to a display client"""
        event_data = {
            "event": "content_assigned",
            "data": {
                "content_id": content_id,
                "display_client_id": display_client_id,
                "lease": lease_data,
                "timestamp": datetime.datetime.now().isoformat()
            },
            "sequenceId": self.get_next_sequence_id()
        }
        
        # Send to dashboard clients for monitoring
        await self.broadcast_to_dashboard_clients(event_data)
        
        # Send assignment to specific display client
        await self.send_to_display_client(display_client_id, {
            "event": "content_assignment",
            "data": {
                "content_id": content_id,
                "lease": lease_data,
                "action": "display_content"
            }
        })

    async def broadcast_lease_renewed(self, content_id: str, display_client_id: str, new_expiry: str):
        """Broadcast when a content lease is renewed"""
        event_data = {
            "event": "lease_renewed",
            "data": {
                "content_id": content_id,
                "display_client_id": display_client_id,
                "new_expiry": new_expiry,
                "timestamp": datetime.datetime.now().isoformat()
            },
            "sequenceId": self.get_next_sequence_id()
        }
        
        await self.broadcast_to_dashboard_clients(event_data)

    async def broadcast_content_released(self, content_id: str, display_client_id: str, reason: str = "lease_expired"):
        """Broadcast when content is released from a display client"""
        event_data = {
            "event": "content_released",
            "data": {
                "content_id": content_id,
                "display_client_id": display_client_id,
                "reason": reason,
                "timestamp": datetime.datetime.now().isoformat()
            },
            "sequenceId": self.get_next_sequence_id()
        }
        
        await self.broadcast_to_dashboard_clients(event_data)

    async def broadcast_epoch_started(self, scene_id: str, epoch_number: int, distribution_stats: dict):
        """Broadcast when a new content distribution epoch begins"""
        event_data = {
            "event": "epoch_started",
            "data": {
                "scene_id": scene_id,
                "epoch": epoch_number,
                "stats": distribution_stats,
                "timestamp": datetime.datetime.now().isoformat()
            },
            "sequenceId": self.get_next_sequence_id()
        }
        
        await self.broadcast_to_dashboard_clients(event_data)

    async def broadcast_queue_status(self, scene_id: str, queue_stats: dict):
        """Broadcast current queue status for a scene"""
        event_data = {
            "event": "queue_status",
            "data": {
                "scene_id": scene_id,
                "queue": queue_stats,
                "timestamp": datetime.datetime.now().isoformat()
            },
            "sequenceId": self.get_next_sequence_id()
        }
        
        await self.broadcast_to_dashboard_clients(event_data)

    async def broadcast_distribution_performance(self, scene_id: str, performance_metrics: dict):
        """Broadcast distribution performance metrics"""
        event_data = {
            "event": "distribution_performance",
            "data": {
                "scene_id": scene_id,
                "metrics": performance_metrics,
                "timestamp": datetime.datetime.now().isoformat()
            },
            "sequenceId": self.get_next_sequence_id()
        }
        
        await self.broadcast_to_dashboard_clients(event_data)

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

class ChannelAssignment(BaseModel):
    channel_id: str
    subchannel_id: Optional[str] = None

class SceneResponse(BaseModel):
    id: str
    name: str
    channels: List[ChannelAssignment]
    overlay: Optional[SceneOverlay] = None
    schedule: Optional[SceneSchedule] = None
    isActive: Optional[bool] = False

class SceneCreateRequest(BaseModel):
    name: str
    channels: List[ChannelAssignment]
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
    redis_distribution: Optional[bool] = False  # Supports Redis distribution
    content_claiming: Optional[bool] = False  # Supports content claiming workflow

class DisplayClientRegistration(BaseModel):
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    hostname: Optional[str] = None  # System hostname (e.g., "colorframe05")
    capabilities: DisplayClientCapabilities
    tags: Optional[List[str]] = None
    client_version: Optional[str] = "1.0.0"  # Client software version
    webhook_port: Optional[int] = None  # Webhook server port for manual updates

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
    hostname: Optional[str]  # System hostname
    is_online: bool
    last_seen: Optional[str]
    assigned_scene_id: Optional[str]
    assigned_scene_name: Optional[str]
    resolution: Optional[List[int]]
    orientation: str
    refresh_rate_hz: Optional[int]
    tags: Optional[List[str]]
    client_version: Optional[str]
    webhook_port: Optional[int]  # Webhook server port
    webhook_url: Optional[str]  # Full webhook URL for manual updates
    redis_distribution: Optional[bool]  # Supports Redis distribution
    content_claiming: Optional[bool]  # Supports content claiming
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

# CORS Configuration - Environment-based origins for security
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://oak:3000,http://127.0.0.1:3000,http://oak,http://localhost,http://127.0.0.1").split(",")
print(f"🌐 CORS configured for origins: {CORS_ORIGINS}")

# Add CORS middleware for React frontend - explicit origins for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    max_age=86400,  # Cache preflight for 24 hours
)

# Discover and load channels on startup
print("🔍 Discovering channels...")
discovered_channels = channel_discovery.discover_channels(app)
print(f"✅ Loaded {len(discovered_channels)} channels")

# Initialize sub-channel manager after channels are loaded
try:
    from subchannel_manager import SubChannelManager
    
    def initialize_subchannel_manager():
        """Initialize sub-channel manager with loaded channels"""
        global subchannel_manager
        if channel_discovery and hasattr(channel_discovery, 'loaded_channels'):
            # Create registry of channel instances
            channel_registry = {}
            for channel_id, channel_data in channel_discovery.loaded_channels.items():
                instance = channel_discovery.get_channel_instance(channel_id)
                if instance:
                    channel_registry[channel_id] = instance
            
            subchannel_manager = SubChannelManager(channel_registry, channel_discovery)
            print(f"✅ SubChannelManager initialized with {len(channel_registry)} channels")
            return True
        return False
    
    # Initialize sub-channel manager now that channels are loaded
    subchannel_manager = None
    if not initialize_subchannel_manager():
        print("⚠️  SubChannelManager initialization failed")
        subchannel_manager = None
    
except ImportError as e:
    print(f"⚠️  Sub-channel functionality not available: {e}")
    subchannel_manager = None

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

# Health endpoint
@app.get("/api/health")
@app.head("/api/health")
async def get_api_health():
    """Get overall API health status"""
    db = SessionLocal()
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_healthy = True
        db_error = None
    except Exception as e:
        db_healthy = False
        db_error = str(e)
    finally:
        db.close()
    
    # Test Redis connection
    redis_status = {"healthy": False, "available": REDIS_AVAILABLE}
    if REDIS_AVAILABLE:
        try:
            redis_manager = get_redis_manager()
            redis_health = await redis_manager.get_health_status()
            redis_status = {
                "healthy": redis_health["status"] == "healthy",
                "available": True,
                "details": redis_health
            }
        except Exception as e:
            redis_status = {
                "healthy": False,
                "available": True,
                "error": str(e)
            }
    
    # Get basic stats
    total_channels = len(channel_discovery.loaded_channels)
    websocket_connections = len(manager.active_connections)
    
    # Overall health status
    overall_healthy = db_healthy and (not REDIS_AVAILABLE or redis_status["healthy"])
    
    health_status = {
        "status": "healthy" if overall_healthy else "unhealthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0",
        "database": {
            "healthy": db_healthy,
            "error": db_error
        },
        "redis": redis_status,
        "channels": {
            "loaded": total_channels,
            "available": list(channel_discovery.loaded_channels.keys())
        },
        "websockets": {
            "active_connections": websocket_connections
        },
        "uptime": "running"  # Simple indicator
    }
    
    return health_status

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

    # Merge in current_settings if present
    current_settings = channel.current_settings or {}
    if "update_interval_unit" in current_settings:
        active_unit = current_settings["update_interval_unit"]
    if "update_interval_value" in current_settings:
        active_value = current_settings["update_interval_value"]

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
    # Also merge any other current_settings values
    for k, v in current_settings.items():
        if k in response and isinstance(response[k], dict):
            response[k]["value"] = v
        elif k not in response:
            response[k] = v
    
    return response

@app.post("/api/channels/{channel_id}/settings")
async def update_channel_settings(
    channel_id: str, 
    settings: Dict[str, Any], 
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Convert string numbers to integers for specific fields
    processed_settings = {}
    for key, value in settings.items():
        if key == "update_interval_value" and isinstance(value, str) and value.isdigit():
            processed_settings[key] = int(value)
        else:
            processed_settings[key] = value
    
    # Merge new settings into existing current_settings
    current = channel.current_settings or {}
    current.update(processed_settings)
    
    # Force SQLAlchemy to detect the JSON change by reassigning
    channel.current_settings = None
    db.flush()
    channel.current_settings = current
    
    # Update status to reflect settings change
    current_status = channel.status or {}
    current_status["lastSettingsUpdate"] = datetime.datetime.now().isoformat()
    channel.status = current_status
    
    db.commit()
    
    # If this is the example_channel and image_choice was updated, create current.jpg
    if channel_id == "example_channel" and "image_choice" in processed_settings:
        try:
            # Get the channel instance to call create_current_image
            channel_instance = channel_discovery.get_channel_instance(channel_id)
            if channel_instance and hasattr(channel_instance, 'create_current_image'):
                await channel_instance.create_current_image(current)
                print(f"Created current.jpg for {channel_id} with image choice: {processed_settings['image_choice']}")
        except Exception as e:
            print(f"Error creating current.jpg for {channel_id}: {e}")
    
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
    
    # If update interval settings changed, notify displays using this channel
    if "update_interval_value" in processed_settings or "update_interval_unit" in processed_settings:
        print(f"Poll interval settings changed for channel {channel_id}, updating affected displays")
        # Find displays that use scenes containing this channel
        scenes_with_channel = db.query(Scene).filter(Scene.channels.contains([channel_id])).all()
        for scene in scenes_with_channel:
            displays_with_scene = db.query(DisplayClient).filter(DisplayClient.assigned_scene_id == scene.id).all()
            for display in displays_with_scene:
                # Calculate new poll interval
                unit = current.get("update_interval_unit", "minutes")
                value = current.get("update_interval_value", 30)
                new_poll_interval = calculate_poll_interval(unit, value)
                
                # Broadcast display status update
                await broadcast_event("display_status_update", {
                    "displayId": display.id,
                    "displayName": display.name,
                    "sceneId": scene.id,
                    "sceneName": scene.name,
                    "newPollInterval": new_poll_interval,
                    "pollIntervalChanged": True
                })
                print(f"Updated poll interval for display {display.id} to {new_poll_interval} seconds")
    
    return {"message": "Settings updated successfully"}

@app.post("/api/channels/{channel_id}/image_request")
async def request_channel_image(
    channel_id: str,
    request_body: ImageRequestBody,
    subchannel_id: Optional[str] = Query(None, description="Optional sub-channel ID"),
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    # Get channel instance
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")

    # Call render_image with optional subchannel_id
    try:
        if subchannel_id:
            # Check if channel supports sub-channels
            if hasattr(channel_instance, 'supports_subchannels') and channel_instance.supports_subchannels():
                image_path = await channel_instance.render_image(
                    resolution=tuple(request_body.resolution),
                    orientation=request_body.orientation,
                    settings={},
                    subchannel_id=subchannel_id
                )
            else:
                raise HTTPException(status_code=400, detail=f"Channel '{channel_id}' does not support sub-channels")
        else:
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
    if subchannel_id:
        current_status["lastSubChannelId"] = subchannel_id
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
        # Enhanced error message for debugging
        available_channels = list(channel_discovery.loaded_channels.keys())
        print(f"🔍 Channel '{channel_id}' not found. Available channels: {available_channels}")
        raise HTTPException(
            status_code=404, 
            detail=f"Channel '{channel_id}' not found. Available: {available_channels}"
        )
    
    try:
        # Check if channel instance has get_status method
        if not hasattr(channel_instance, 'get_status'):
            print(f"⚠️  Channel '{channel_id}' instance missing get_status() method")
            # Fallback status
            config = getattr(channel_instance, 'config', {})
            health = {
                "channelId": channel_id,
                "name": config.get("name", channel_id),
                "version": config.get("version", "unknown"),
                "status": {"active": True, "lastUpdate": None, "lastError": "get_status() method not implemented"},
                "healthy": False,
                "lastCheck": datetime.datetime.now().isoformat(),
                "warning": "Channel instance missing get_status() method"
            }
            return health
        
        status = channel_instance.get_status()
        config = getattr(channel_instance, 'config', {})
        
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
        print(f"❌ Health check failed for channel '{channel_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/api/channels/{channel_id}/current.jpg")
async def get_channel_current_image_file(channel_id: str):
    """Serve the channel's current image file (for channels that place current.jpg in root)"""
    try:
        # Get channel data
        channel_data = channel_discovery.loaded_channels.get(channel_id)
        if not channel_data:
            raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
        
        channel_path = channel_data['path']
        config = channel_data['config']
        
        # Get current image filename from config (defaults to current.jpg)
        current_image_filename = config.get("current_image", "current.jpg")
        current_image_path = channel_path / current_image_filename
        
        # Check if file exists
        if not current_image_path.exists():
            raise HTTPException(status_code=404, detail=f"Current image not found: {current_image_filename}")
        
        # Determine MIME type based on file extension
        file_extension = current_image_path.suffix.lower()
        if file_extension in ['.jpg', '.jpeg']:
            media_type = "image/jpeg"
        elif file_extension == '.png':
            media_type = "image/png"
        elif file_extension == '.gif':
            media_type = "image/gif"
        elif file_extension == '.webp':
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"  # Default fallback
        
        # Return the file with correct headers for inline display
        return FileResponse(
            path=str(current_image_path),
            media_type=media_type,
            headers={
                "Content-Disposition": "inline",  # Display in browser, don't force download
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error serving current image for channel '{channel_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve current image: {str(e)}")

@app.get("/api/channels/{channel_id}/current")
async def get_channel_current_image_generic(channel_id: str):
    """Generic endpoint to serve the channel's current image (auto-detects file type)"""
    try:
        # Get channel data
        channel_data = channel_discovery.loaded_channels.get(channel_id)
        if not channel_data:
            raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
        
        channel_path = channel_data['path']
        config = channel_data['config']
        
        # Get current image filename from config (defaults to current.jpg)
        current_image_filename = config.get("current_image", "current.jpg")
        current_image_path = channel_path / current_image_filename
        
        # Check if file exists
        if not current_image_path.exists():
            raise HTTPException(status_code=404, detail=f"Current image not found: {current_image_filename}")
        
        # Determine MIME type based on file extension
        file_extension = current_image_path.suffix.lower()
        if file_extension in ['.jpg', '.jpeg']:
            media_type = "image/jpeg"
        elif file_extension == '.png':
            media_type = "image/png"
        elif file_extension == '.gif':
            media_type = "image/gif"
        elif file_extension == '.webp':
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"  # Default fallback
        
        # Return the file with correct headers for inline display
        return FileResponse(
            path=str(current_image_path),
            media_type=media_type,
            headers={
                "Content-Disposition": "inline",  # Display in browser, don't force download
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error serving current image for channel '{channel_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve current image: {str(e)}")

@app.get("/api/channels/{channel_id}/current/{resolution}/{filename}")
async def get_channel_current_image_by_resolution(channel_id: str, resolution: str, filename: str):
    """Serve resolution-specific images from current/{resolution}/ subfolders"""
    try:
        # Get channel data
        channel_data = channel_discovery.loaded_channels.get(channel_id)
        if not channel_data:
            raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
        
        channel_path = channel_data['path']
        
        # Validate resolution format (should be like "800x480")
        if not resolution.count('x') == 1:
            raise HTTPException(status_code=400, detail=f"Invalid resolution format: {resolution}")
        
        try:
            width, height = resolution.split('x')
            int(width), int(height)  # Validate they're numbers
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid resolution format: {resolution}")
        
        # Build path to resolution-specific image
        current_image_path = channel_path / "current" / resolution / filename
        
        # Check if file exists
        if not current_image_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Image not found: {filename} at resolution {resolution}"
            )
        
        # Determine MIME type based on file extension
        file_extension = current_image_path.suffix.lower()
        if file_extension in ['.jpg', '.jpeg']:
            media_type = "image/jpeg"
        elif file_extension == '.png':
            media_type = "image/png"
        elif file_extension == '.gif':
            media_type = "image/gif"
        elif file_extension == '.webp':
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"  # Default fallback
        
        # Return the file with correct headers for inline display
        return FileResponse(
            path=str(current_image_path),
            media_type=media_type,
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
                "X-Resolution": resolution,  # Header to indicate which resolution is served
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error serving resolution-specific image for channel '{channel_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve resolution-specific image: {str(e)}")

# Debug endpoint to see loaded channels
@app.get("/api/admin/channels/debug")
async def debug_loaded_channels():
    """Debug endpoint to see what channels are currently loaded in memory"""
    loaded = {}
    for channel_id, channel_data in channel_discovery.loaded_channels.items():
        instance = channel_data.get('instance')
        config = channel_data.get('config', {})
        
        loaded[channel_id] = {
            "has_instance": instance is not None,
            "instance_type": type(instance).__name__ if instance else None,
            "has_get_status": hasattr(instance, 'get_status') if instance else False,
            "config_name": config.get('name', 'Unknown'),
            "config_version": config.get('version', 'Unknown'),
            "config_id": config.get('id', 'Not specified'),
            "directory_path": str(channel_data.get('path', 'Unknown'))
        }
    
    return {
        "loaded_channels_count": len(channel_discovery.loaded_channels),
        "loaded_channels": loaded,
        "channels_directory": str(channel_discovery.channels_dir)
    }

# Debug endpoint to test loading a specific channel
@app.post("/api/admin/channels/{channel_id}/reload")
async def reload_specific_channel(channel_id: str):
    """Debug endpoint to reload a specific channel and see detailed error messages"""
    try:
        # Find the channel directory
        channels_dir = Path("channels")
        channel_found = None
        
        for channel_path in channels_dir.iterdir():
            if channel_path.is_dir():
                config = channel_discovery.load_channel_config(channel_path)
                if config:
                    resolved_id = config.get('id', channel_path.name)
                    if resolved_id == channel_id:
                        channel_found = channel_path
                        break
        
        if not channel_found:
            return {
                "success": False,
                "error": f"Channel directory not found for ID: {channel_id}",
                "available_directories": [p.name for p in channels_dir.iterdir() if p.is_dir()]
            }
        
        # Try to load the channel
        print(f"🔄 Attempting to reload channel: {channel_id} from {channel_found}")
        config = channel_discovery.load_channel_config(channel_found)
        instance = channel_discovery.load_channel_class(channel_found)
        
        # Update loaded channels
        channel_discovery.loaded_channels[channel_id] = {
            'config': config,
            'instance': instance,
            'path': channel_found
        }
        
        return {
            "success": True,
            "channel_id": channel_id,
            "directory_path": str(channel_found),
            "config_loaded": config is not None,
            "instance_loaded": instance is not None,
            "instance_type": type(instance).__name__ if instance else None,
            "has_get_status": hasattr(instance, 'get_status') if instance else False,
            "config_summary": {
                "name": config.get('name', 'Unknown') if config else None,
                "version": config.get('version', 'Unknown') if config else None,
                "id": config.get('id', 'Not specified') if config else None
            }
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

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

# Development/Admin endpoint to reload channels (useful when IDs change)
@app.post("/api/admin/reload-channels")
async def reload_channels():
    """Reload all channels from filesystem - useful for development when channel IDs change"""
    try:
        # Clear current loaded channels
        channel_discovery.loaded_channels.clear()
        
        # Re-discover channels
        print("🔄 Reloading channels...")
        discovered_channels = channel_discovery.discover_channels(app)
        print(f"✅ Reloaded {len(discovered_channels)} channels")
        
        # Sync with database
        def sync_reloaded_channels():
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
                            channel_dir=channel_data['channel_dir']
                        )
                        db.add(new_channel)
                        print(f"➕ Added new channel to DB: {channel_id}")
                
                db.commit()
                print("💾 Database sync completed")
            except Exception as e:
                db.rollback()
                print(f"❌ Database sync failed: {e}")
                raise
            finally:
                db.close()
        
        sync_reloaded_channels()
        
        return {
            "success": True,
            "message": f"Successfully reloaded {len(discovered_channels)} channels",
            "channels": [ch['id'] for ch in discovered_channels]
        }
        
    except Exception as e:
        print(f"❌ Channel reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload channels: {str(e)}")

# Admin endpoint to remove channel from database (filesystem untouched)
@app.delete("/api/admin/channels/{channel_id}")
async def remove_channel_from_database(channel_id: str, db: Session = Depends(get_db)):
    """Remove channel from database without touching filesystem - useful for cleanup of orphaned entries"""
    try:
        # Check if channel exists in database
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found in database")
        
        # Check if channel has any associated scenes that might be using it
        # We'll allow deletion but warn about potential impacts
        channel_name = channel.name
        
        # Check for any scenes using this channel (optional warning)
        # Use JSON contains query since channels is a JSON array
        scenes_using_channel = db.query(Scene).filter(Scene.channels.contains([channel_id])).all()
        warning_message = None
        if scenes_using_channel:
            scene_names = [scene.name for scene in scenes_using_channel]
            warning_message = f"Warning: {len(scenes_using_channel)} scene(s) are using this channel: {', '.join(scene_names)}"
        
        # Remove the channel from database
        db.delete(channel)
        db.commit()
        
        # Also remove from loaded channels if present
        if channel_id in channel_discovery.loaded_channels:
            del channel_discovery.loaded_channels[channel_id]
            print(f"🗑️  Removed channel from loaded channels: {channel_id}")
        
        print(f"🗑️  Removed channel from database: {channel_id} ({channel_name})")
        
        response = {
            "success": True,
            "message": f"Successfully removed channel '{channel_id}' ({channel_name}) from database",
            "channelId": channel_id,
            "channelName": channel_name
        }
        
        if warning_message:
            response["warning"] = warning_message
            
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to remove channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove channel from database: {str(e)}")

# Endpoint to list orphaned database channels (channels in DB but not on filesystem)
@app.get("/api/admin/channels/orphaned")
async def list_orphaned_channels(db: Session = Depends(get_db)):
    """List channels that exist in database but not on filesystem"""
    try:
        # Get all channels from database
        db_channels = db.query(Channel).all()
        
        # Get all channels from filesystem
        filesystem_channels = set()
        channels_dir = Path("channels")
        if channels_dir.exists():
            for channel_path in channels_dir.iterdir():
                if channel_path.is_dir():
                    config_file = channel_path / "config.json"
                    if config_file.exists():
                        try:
                            with open(config_file, 'r') as f:
                                config = json.load(f)
                                # Use same logic as discovery: prefer config ID over directory name
                                channel_id = config.get('id', channel_path.name)
                                filesystem_channels.add(channel_id)
                        except Exception as e:
                            print(f"Error reading config for {channel_path.name}: {e}")
        
        # Find orphaned channels (in DB but not on filesystem)
        orphaned = []
        for db_channel in db_channels:
            if db_channel.id not in filesystem_channels:
                # Check if this channel has any scenes using it
                # Use JSON contains query since channels is a JSON array
                scenes_count = db.query(Scene).filter(Scene.channels.contains([db_channel.id])).count()
                
                orphaned.append({
                    "id": db_channel.id,
                    "name": db_channel.name,
                    "version": db_channel.version,
                    "description": db_channel.description,
                    "channel_dir": db_channel.channel_dir,
                    "scenes_using": scenes_count
                })
        
        return {
            "orphaned_channels": orphaned,
            "count": len(orphaned),
            "total_db_channels": len(db_channels),
            "total_filesystem_channels": len(filesystem_channels)
        }
        
    except Exception as e:
        print(f"❌ Failed to list orphaned channels: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list orphaned channels: {str(e)}")

# Admin endpoint to reset channels database from filesystem
@app.post("/api/admin/channels/reset")
async def reset_channels_database(db: Session = Depends(get_db)):
    """Reset channels database: remove all channel entries and rebuild from filesystem only"""
    try:
        print("🔄 Starting channels database reset...")
        
        # Get current database state for reporting
        current_channels = db.query(Channel).all()
        current_count = len(current_channels)
        current_ids = [ch.id for ch in current_channels]
        
        # Check for scenes that will be affected
        affected_scenes = []
        for channel in current_channels:
            # Use JSON contains query since channels is a JSON array
            scenes = db.query(Scene).filter(Scene.channels.contains([channel.id])).all()
            for scene in scenes:
                affected_scenes.append({
                    "scene_id": scene.id,
                    "scene_name": scene.name,
                    "channel_id": channel.id,
                    "channel_name": channel.name
                })
        
        # Clear ALL channels from database
        db.query(Channel).delete()
        db.commit()
        print(f"🗑️  Removed {current_count} channels from database")
        
        # Clear loaded channels from memory
        channel_discovery.loaded_channels.clear()
        print("🧹 Cleared loaded channels from memory")
        
        # Re-discover channels from filesystem only
        print("🔍 Re-discovering channels from filesystem...")
        discovered_channels = channel_discovery.discover_channels(app)
        filesystem_count = len(discovered_channels)
        filesystem_ids = [ch['id'] for ch in discovered_channels]
        
        # Rebuild database from discovered channels
        added_channels = []
        for channel_data in discovered_channels:
            channel_id = channel_data['id']
            config = channel_data['config']
            
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
                channel_dir=channel_data['channel_dir']
            )
            db.add(new_channel)
            added_channels.append({
                "id": channel_id,
                "name": config.get('name', channel_id),
                "version": config.get('version', '1.0.0')
            })
            print(f"➕ Added channel to DB: {channel_id}")
        
        db.commit()
        print("💾 Database rebuild completed")
        
        # Calculate changes
        removed_ids = set(current_ids) - set(filesystem_ids)
        added_ids = set(filesystem_ids) - set(current_ids)
        kept_ids = set(current_ids) & set(filesystem_ids)
        
        return {
            "success": True,
            "message": f"Successfully reset channels database from filesystem",
            "summary": {
                "before": {
                    "total_channels": current_count,
                    "channel_ids": current_ids
                },
                "after": {
                    "total_channels": filesystem_count,
                    "channel_ids": filesystem_ids
                },
                "changes": {
                    "removed_count": len(removed_ids),
                    "removed_ids": list(removed_ids),
                    "added_count": len(added_ids), 
                    "added_ids": list(added_ids),
                    "kept_count": len(kept_ids),
                    "kept_ids": list(kept_ids)
                }
            },
            "affected_scenes": affected_scenes,
            "warnings": [
                f"{len(affected_scenes)} scene(s) may need channel reassignment" if affected_scenes else None
            ]
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Channel database reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset channels database: {str(e)}")

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
    
    def convert_channels(scene_channels):
        """Convert channels to new format with backward compatibility"""
        channels_data = []
        for channel in (scene_channels or []):
            if isinstance(channel, str):
                # Old format: just channel ID
                channels_data.append(ChannelAssignment(channel_id=channel))
            elif isinstance(channel, dict):
                # New format: channel assignment object
                channels_data.append(ChannelAssignment(
                    channel_id=channel["channel_id"],
                    subchannel_id=channel.get("subchannel_id")
                ))
            else:
                # Fallback for unexpected format
                channels_data.append(ChannelAssignment(channel_id=str(channel)))
        return channels_data
    
    result = [
        SceneResponse(
            id=s.id,
            name=s.name,
            channels=convert_channels(s.channels),
            overlay=s.overlay,
            schedule=s.schedule,
            isActive=s.is_active
        ) for s in scenes
    ]
    
    return {
        "scenes": result,
        "meta": PaginationMeta(total=total, limit=limit, offset=offset)
    }

def validate_scene_channel_assignments(channel_assignments: List[ChannelAssignment]) -> List[str]:
    """
    Validate scene channel assignments for subchannel requirements.
    
    Returns list of validation errors. Empty list means validation passed.
    """
    errors = []
    
    for assignment in channel_assignments:
        channel_id = assignment.channel_id
        subchannel_id = assignment.subchannel_id
        
        # Get channel instance to check if it supports subchannels
        try:
            channel_instance = channel_discovery.get_channel_instance(channel_id)
            if not channel_instance:
                errors.append(f"Channel '{channel_id}' not found or not loaded")
                continue
            
            # Check if channel supports subchannels
            supports_subchannels = hasattr(channel_instance, 'supports_subchannels') and channel_instance.supports_subchannels()
            
            if supports_subchannels and not subchannel_id:
                # This channel requires a subchannel but none was provided
                errors.append(f"Channel '{channel_id}' supports subchannels and requires a subchannel to be selected")
            elif not supports_subchannels and subchannel_id:
                # This channel doesn't support subchannels but one was provided
                errors.append(f"Channel '{channel_id}' does not support subchannels, but subchannel '{subchannel_id}' was specified")
            elif supports_subchannels and subchannel_id:
                # Validate that the specified subchannel exists
                try:
                    subchannels = channel_instance.get_subchannels()
                    valid_subchannel_ids = [sc['id'] for sc in subchannels]
                    if subchannel_id not in valid_subchannel_ids:
                        errors.append(f"Subchannel '{subchannel_id}' not found in channel '{channel_id}'. Available subchannels: {', '.join(valid_subchannel_ids)}")
                except Exception as e:
                    errors.append(f"Error validating subchannel '{subchannel_id}' for channel '{channel_id}': {str(e)}")
                    
        except Exception as e:
            errors.append(f"Error validating channel '{channel_id}': {str(e)}")
    
    return errors

@app.post("/api/scenes")
async def create_scene(scene_data: SceneCreateRequest, db: Session = Depends(get_db)):
    # Validate channel assignments for subchannel requirements
    validation_errors = validate_scene_channel_assignments(scene_data.channels)
    if validation_errors:
        raise HTTPException(
            status_code=400, 
            detail={
                "message": "Scene validation failed",
                "errors": validation_errors
            }
        )
    # Generate ID from name
    scene_id = scene_data.name.lower().replace(" ", "-")
    
    # Check if scene exists
    existing = db.query(Scene).filter(Scene.id == scene_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Scene with this name already exists")
    
    # Convert channel assignments to storage format
    channels_data = []
    for assignment in scene_data.channels:
        if isinstance(assignment, str):
            # Backward compatibility: if string provided, convert to assignment
            channels_data.append({"channel_id": assignment})
        else:
            # New format: store channel assignment with optional subchannel
            channel_assignment = {"channel_id": assignment.channel_id}
            if assignment.subchannel_id:
                channel_assignment["subchannel_id"] = assignment.subchannel_id
            channels_data.append(channel_assignment)
    
    db_scene = Scene(
        id=scene_id,
        name=scene_data.name,
        channels=channels_data,
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
        "channels": channels_data
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
    
    # Handle backward compatibility for channels format
    channels_data = []
    for channel in (scene.channels or []):
        if isinstance(channel, str):
            # Old format: just channel ID
            channels_data.append(ChannelAssignment(channel_id=channel))
        elif isinstance(channel, dict):
            # New format: channel assignment object
            channels_data.append(ChannelAssignment(
                channel_id=channel["channel_id"],
                subchannel_id=channel.get("subchannel_id")
            ))
        else:
            # Fallback for unexpected format
            channels_data.append(ChannelAssignment(channel_id=str(channel)))
    
    return SceneResponse(
        id=scene.id,
        name=scene.name,
        channels=channels_data,
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
    # Validate channel assignments for subchannel requirements
    validation_errors = validate_scene_channel_assignments(scene_data.channels)
    if validation_errors:
        raise HTTPException(
            status_code=400, 
            detail={
                "message": "Scene validation failed",
                "errors": validation_errors
            }
        )
        
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Convert channel assignments to storage format
    channels_data = []
    for assignment in scene_data.channels:
        if isinstance(assignment, str):
            # Backward compatibility: if string provided, convert to assignment
            channels_data.append({"channel_id": assignment})
        else:
            # New format: store channel assignment with optional subchannel
            channel_assignment = {"channel_id": assignment.channel_id}
            if assignment.subchannel_id:
                channel_assignment["subchannel_id"] = assignment.subchannel_id
            channels_data.append(channel_assignment)
    
    scene.name = scene_data.name
    scene.channels = channels_data
    scene.overlay = scene_data.overlay.dict() if scene_data.overlay else None
    scene.schedule = scene_data.schedule.dict() if scene_data.schedule else None
    
    db.commit()
    
    # Broadcast WebSocket event
    await broadcast_event("scene_updated", {
        "sceneId": scene_id,
        "sceneName": scene_data.name,
        "channels": channels_data
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
        hostname=registration.hostname,
        resolution=registration.capabilities.resolution,
        supported_formats=registration.capabilities.supported_formats,
        orientation=registration.capabilities.orientation,
        refresh_rate_hz=registration.capabilities.refresh_rate_hz,
        client_version=registration.client_version,
        webhook_port=registration.webhook_port,
        redis_distribution=registration.capabilities.redis_distribution,
        content_claiming=registration.capabilities.content_claiming,
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
        hostname=display_client.hostname,
        is_online=display_client.is_online,
        last_seen=display_client.last_seen.isoformat() if display_client.last_seen else None,
        assigned_scene_id=display_client.assigned_scene_id,
        assigned_scene_name=None,
        resolution=display_client.resolution,
        orientation=display_client.orientation,
        refresh_rate_hz=display_client.refresh_rate_hz,
        tags=display_client.tags,
        client_version=display_client.client_version,
        webhook_port=display_client.webhook_port,
        webhook_url=f"http://{display_client.hostname}:{display_client.webhook_port}" if display_client.hostname and display_client.webhook_port else None,
        redis_distribution=display_client.redis_distribution,
        content_claiming=display_client.content_claiming,
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
            hostname=getattr(client, 'hostname', None),
            is_online=client.is_online,
            last_seen=client.last_seen.isoformat() if client.last_seen else None,
            assigned_scene_id=client.assigned_scene_id,
            assigned_scene_name=scene_names.get(client.assigned_scene_id),
            resolution=client.resolution,
            orientation=client.orientation,
            refresh_rate_hz=client.refresh_rate_hz,
            tags=client.tags,
            client_version=client.client_version,
            webhook_port=getattr(client, 'webhook_port', None),
            webhook_url=f"http://{getattr(client, 'hostname', 'unknown')}:{getattr(client, 'webhook_port', 8080)}" if getattr(client, 'hostname', None) and getattr(client, 'webhook_port', None) else None,
            redis_distribution=getattr(client, 'redis_distribution', None),
            content_claiming=getattr(client, 'content_claiming', None),
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
    request: Request,
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

    # Check for conditional request using If-None-Match header
    if_none_match = request.headers.get("if-none-match")
    current_change_token = image_info.get("change_token")
    
    # If client has the same change token, return 304 Not Modified
    if if_none_match and current_change_token and if_none_match == current_change_token:
        return Response(status_code=304)

    response_data = {
        "display_id": display_id,
        "scene_id": scene.id,
        "scene_name": scene.name,
        "image_url": image_info["url"],
        "image_path": image_info["path"],
        "resolution": image_info["resolution"],
        "generated_at": image_info["generated_at"],
        "channels": image_info["channels_rendered"],
        "cache_expires_in": image_info["cache_expires_in"],
        # New change detection fields
        "last_modified": image_info["last_modified"],
        "content_hash": image_info["content_hash"], 
        "change_token": image_info["change_token"],
        "file_size": image_info["file_size"],
        "file_exists": image_info["file_exists"]
    }
    
    # Set ETag header for future conditional requests
    response = Response(
        content=json.dumps(response_data),
        media_type="application/json"
    )
    if current_change_token:
        response.headers["ETag"] = current_change_token
        response.headers["Cache-Control"] = "private, must-revalidate"
    
    return response

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
            # Handle both old and new channel format
            first_channel = assigned_scene.channels[0]
            if isinstance(first_channel, str):
                # Old format: just channel ID
                channel_id = first_channel
                subchannel_id = None
            elif isinstance(first_channel, dict):
                # New format: channel assignment object
                channel_id = first_channel["channel_id"]
                subchannel_id = first_channel.get("subchannel_id")
            else:
                # Fallback
                channel_id = str(first_channel)
                subchannel_id = None
                
            # Get channel from database to access current_settings
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if channel:
                # Use current_settings from database, fallback to config defaults
                current_settings = channel.current_settings or {}
                
                # Load default values from config if not in current_settings
                channel_config_path = Path("channels") / channel_id / "config.json"
                defaults = {}
                if channel_config_path.exists():
                    import json
                    with open(channel_config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    settings_schema = config.get("settings", {})
                    for setting_key, setting_def in settings_schema.items():
                        defaults[setting_key] = setting_def.get("default")
                
                # Get current values or fallback to defaults
                unit = current_settings.get("update_interval_unit", defaults.get("update_interval_unit", "minutes"))
                value = current_settings.get("update_interval_value", defaults.get("update_interval_value", 30))
                
                # Calculate poll interval
                poll_interval = calculate_poll_interval(unit, value)

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

@app.post("/api/displays/{display_id}/update")
async def trigger_display_update(
    display_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Trigger immediate update on a display client via webhook"""
    
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    if not display_client.hostname or not display_client.webhook_port:
        raise HTTPException(
            status_code=400, 
            detail="Display client does not have webhook capability configured"
        )
    
    webhook_url = f"http://{display_client.hostname}:{display_client.webhook_port}/update"
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            payload = {"reason": reason or "API triggered update", "timestamp": datetime.datetime.now().isoformat()}
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            
            # Broadcast update event
            await broadcast_event("display_manual_update", {
                "displayId": display_id,
                "displayName": display_client.name,
                "action": "update",
                "reason": reason,
                "webhook_url": webhook_url,
                "triggeredBy": {
                    "source": "api",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            })
            
            return {
                "message": f"Update triggered on display {display_client.name}",
                "display_id": display_id,
                "webhook_response": response.json() if response.content else None
            }
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Failed to reach display webhook: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502, 
            detail=f"Display webhook returned error: {e.response.status_code}"
        )

@app.post("/api/displays/{display_id}/refresh")
async def trigger_display_refresh(
    display_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Trigger immediate refresh (bypassing cache) on a display client via webhook"""
    
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    if not display_client.hostname or not display_client.webhook_port:
        raise HTTPException(
            status_code=400, 
            detail="Display client does not have webhook capability configured"
        )
    
    webhook_url = f"http://{display_client.hostname}:{display_client.webhook_port}/refresh"
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            payload = {"reason": reason or "API triggered refresh", "timestamp": datetime.datetime.now().isoformat()}
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            
            # Broadcast refresh event
            await broadcast_event("display_manual_update", {
                "displayId": display_id,
                "displayName": display_client.name,
                "action": "refresh",
                "reason": reason,
                "webhook_url": webhook_url,
                "triggeredBy": {
                    "source": "api",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            })
            
            return {
                "message": f"Refresh triggered on display {display_client.name}",
                "display_id": display_id,
                "webhook_response": response.json() if response.content else None
            }
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Failed to reach display webhook: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502, 
            detail=f"Display webhook returned error: {e.response.status_code}"
        )

@app.get("/api/displays/{display_id}/webhook_status")
async def get_display_webhook_status(
    display_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """Get webhook status from a display client"""
    
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    if not display_client.hostname or not display_client.webhook_port:
        return {
            "webhook_available": False,
            "reason": "Display client does not have webhook capability configured"
        }
    
    webhook_url = f"http://{display_client.hostname}:{display_client.webhook_port}/status"
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(webhook_url, timeout=5.0)
            response.raise_for_status()
            
            return {
                "webhook_available": True,
                "webhook_url": webhook_url,
                "display_status": response.json(),
                "last_checked": datetime.datetime.now().isoformat()
            }
            
    except httpx.RequestError as e:
        return {
            "webhook_available": False,
            "webhook_url": webhook_url,
            "error": f"Connection failed: {str(e)}",
            "last_checked": datetime.datetime.now().isoformat()
        }
    except httpx.HTTPStatusError as e:
        return {
            "webhook_available": False,
            "webhook_url": webhook_url,
            "error": f"HTTP error: {e.response.status_code}",
            "last_checked": datetime.datetime.now().isoformat()
        }

@app.get("/api/displays/discover")
async def discover_displays_mdns(
    timeout: int = 5,
    _: dict = Depends(check_rate_limit)
):
    """Discover displays on the network via mDNS"""
    try:
        from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
        import threading
        import time
        
        discovered_displays = []
        discovery_complete = threading.Event()
        
        class DisplayServiceListener(ServiceListener):
            def add_service(self, zeroconf, type, name):
                if '_mimir-display._tcp.local.' in name:
                    info = zeroconf.get_service_info(type, name)
                    if info:
                        # Extract service properties
                        properties = {}
                        if info.properties:
                            for key, value in info.properties.items():
                                try:
                                    properties[key.decode('utf-8')] = value.decode('utf-8')
                                except:
                                    pass
                        
                        # Get IP addresses
                        addresses = [addr for addr in info.addresses if addr]
                        
                        display_info = {
                            "service_name": name,
                            "hostname": properties.get("hostname", "unknown"),
                            "display_name": properties.get("display_name", "Unknown Display"),
                            "display_id": properties.get("display_id"),
                            "location": properties.get("location"),
                            "resolution": properties.get("resolution"),
                            "client_version": properties.get("client_version"),
                            "webhook_port": int(properties.get("webhook_port", 0)) if properties.get("webhook_port") else None,
                            "addresses": [addr.decode('utf-8') if isinstance(addr, bytes) else str(addr) for addr in addresses],
                            "port": info.port,
                            "discovered_at": datetime.datetime.now().isoformat()
                        }
                        
                        # Add webhook URL if available
                        if display_info["addresses"] and display_info["webhook_port"]:
                            display_info["webhook_url"] = f"http://{display_info['addresses'][0]}:{display_info['webhook_port']}"
                        
                        discovered_displays.append(display_info)
            
            def remove_service(self, zeroconf, type, name):
                pass
            
            def update_service(self, zeroconf, type, name):
                pass
        
        # Start discovery
        zeroconf = Zeroconf()
        listener = DisplayServiceListener()
        browser = ServiceBrowser(zeroconf, "_mimir-display._tcp.local.", listener)
        
        # Wait for discovery timeout
        time.sleep(timeout)
        
        # Cleanup
        browser.cancel()
        zeroconf.close()
        
        return {
            "discovered_displays": discovered_displays,
            "discovery_timeout": timeout,
            "total_found": len(discovered_displays),
            "discovery_completed_at": datetime.datetime.now().isoformat()
        }
        
    except ImportError:
        raise HTTPException(
            status_code=501, 
            detail="mDNS discovery not available (zeroconf library not installed)"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Discovery failed: {str(e)}"
        )

def calculate_poll_interval(update_interval_unit: str, update_interval_value: int) -> int:
    """Calculate poll interval in seconds from unit and value"""
    unit = str(update_interval_unit).strip().lower()
    multipliers = {
        'seconds': 1,
        'minutes': 60,
        'hours': 3600,
        'days': 86400
    }
    return int(update_interval_value) * multipliers.get(unit, 60)

async def get_file_metadata(file_path: str) -> dict:
    """Get file metadata for change detection"""
    try:
        full_path = Path(file_path)
        if not full_path.exists():
            return {
                "exists": False,
                "last_modified": None,
                "content_hash": None,
                "size": 0
            }
        
        # Get file stats
        stat = full_path.stat()
        last_modified = datetime.datetime.fromtimestamp(stat.st_mtime)
        file_size = stat.st_size
        
        # Calculate content hash
        content_hash = hashlib.md5()
        with open(full_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                content_hash.update(chunk)
        
        return {
            "exists": True,
            "last_modified": last_modified.isoformat(),
            "content_hash": content_hash.hexdigest(),
            "size": file_size
        }
    except Exception as e:
        print(f"Error getting file metadata for {file_path}: {e}")
        return {
            "exists": False,
            "last_modified": None,
            "content_hash": None,
            "size": 0,
            "error": str(e)
        }

async def generate_scene_image_for_display(scene, display_client):
    """Generate scene image optimized for specific display client"""
    
    # Get display resolution and orientation
    resolution = display_client.resolution or [1920, 1080]
    orientation = display_client.orientation or "landscape"

    # Use the first channel in the scene
    if scene.channels:
        first_channel = scene.channels[0]
        if isinstance(first_channel, str):
            # Old format: just channel ID
            channel_id = first_channel
            subchannel_id = None
        elif isinstance(first_channel, dict):
            # New format: channel assignment object
            channel_id = first_channel["channel_id"]
            subchannel_id = first_channel.get("subchannel_id")
        else:
            # Fallback
            channel_id = str(first_channel)
            subchannel_id = None
    else:
        channel_id = "example_channel"
        subchannel_id = None
    
    # Get channel instance to trigger resolution-aware image generation
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if channel_instance and hasattr(channel_instance, 'render_image'):
        try:
            # Call channel's render_image method with display-specific resolution
            # Get current channel settings from database
            db = SessionLocal()
            try:
                channel_record = db.query(Channel).filter(Channel.id == channel_id).first()
                settings = channel_record.current_settings if channel_record else {}
            finally:
                db.close()
            
            # Generate image optimized for this display's resolution
            if subchannel_id and hasattr(channel_instance, 'supports_subchannels') and channel_instance.supports_subchannels():
                # Channel supports sub-channels, pass subchannel_id
                await channel_instance.render_image(
                    resolution=tuple(resolution),
                    orientation=orientation,
                    settings=settings or {},
                    subchannel_id=subchannel_id
                )
                print(f"✅ Generated image for {channel_id} sub-channel {subchannel_id} at resolution {resolution}")
            else:
                # Standard channel rendering
                await channel_instance.render_image(
                    resolution=tuple(resolution),
                    orientation=orientation,
                    settings=settings or {}
                )
                print(f"✅ Generated image for {channel_id} at resolution {resolution}")
            
        except Exception as e:
            print(f"⚠️  Failed to generate image for {channel_id}: {e}")
            # Continue with existing file lookup as fallback
    
    # Get channel config for resolution-specific image path
    if channel_instance and hasattr(channel_instance, 'config'):
        # Get the actual channel directory path from the discovery system
        channel_data = channel_discovery.loaded_channels.get(channel_id)
        if channel_data and 'path' in channel_data:
            # Use resolution-based subfolder structure: current/{width}x{height}/current.jpg
            channel_dir = channel_data['path']
            current_image_filename = channel_instance.config.get("current_image", "current.jpg")
            resolution_folder = f"{resolution[0]}x{resolution[1]}"
            image_path = str(channel_dir / "current" / resolution_folder / current_image_filename)
            # URL uses resolution-specific path
            image_url = f"/api/channels/{channel_id}/current/{resolution_folder}/{current_image_filename}"
        else:
            # Fallback with resolution folder
            resolution_folder = f"{resolution[0]}x{resolution[1]}"
            image_path = f"channels/{channel_id}/current/{resolution_folder}/current.jpg"
            image_url = f"/api/channels/{channel_id}/current/{resolution_folder}/current.jpg"
    else:
        # Fallback to assets subdirectory for channels without config
        image_url = f"/api/channels/{channel_id}/assets/current.jpg"
        image_path = f"channels/{channel_id}/assets/current.jpg"

    # Get file metadata for change detection
    file_metadata = await get_file_metadata(image_path)
    
    # Generate a change detection token based on file content and metadata
    change_token = None
    if file_metadata["exists"]:
        # Create a unique token based on file hash and last modified time
        token_source = f"{file_metadata['content_hash']}:{file_metadata['last_modified']}:{file_metadata['size']}"
        change_token = hashlib.sha256(token_source.encode()).hexdigest()[:16]

    image_info = {
        "url": image_url,
        "path": image_path,
        "resolution": resolution,
        "generated_at": datetime.datetime.now().isoformat(),
        "cache_expires_in": 300,
        "channels_rendered": scene.channels or [],
        "orientation": orientation,
        # New change detection fields
        "last_modified": file_metadata["last_modified"],
        "content_hash": file_metadata["content_hash"],
        "change_token": change_token,
        "file_size": file_metadata["size"],
        "file_exists": file_metadata["exists"]
    }

    # Update display client's current image path
    db = SessionLocal()
    try:
        display_client.current_image_path = image_path
        db.commit()
    finally:
        db.close()

    return image_info


# =========================================================================
# Sub-Channel Management Endpoints (v2.4+)
# =========================================================================

@app.get("/api/channels/{channel_id}/subchannels/config")
async def get_subchannel_config(channel_id: str, include_subchannels: bool = False):
    """
    Get sub-channel configuration for a channel
    
    Args:
        channel_id: Channel ID
        include_subchannels: Whether to include the actual subchannel list (default: False)
    
    Returns:
        Configuration with validation requirements and optionally subchannel list
    """
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    return await subchannel_manager.get_subchannel_config(channel_id, include_subchannels)


@app.get("/api/channels/{channel_id}/subchannels")
async def list_subchannels(channel_id: str):
    """List all sub-channels for a channel"""
    if not subchannel_manager:
        return {"subChannels": []}  # Graceful fallback
    
    return await subchannel_manager.list_subchannels(channel_id)


@app.get("/api/channels/{channel_id}/subchannels/{subchannel_id}")
async def get_subchannel_details(channel_id: str, subchannel_id: str):
    """Get details for a specific sub-channel"""
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    return await subchannel_manager.get_subchannel_details(channel_id, subchannel_id)


@app.post("/api/channels/{channel_id}/subchannels")
async def create_subchannel(channel_id: str, request: Request):
    """Create a new sub-channel"""
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    
    return await subchannel_manager.create_subchannel(channel_id, data)


@app.put("/api/channels/{channel_id}/subchannels/{subchannel_id}")
async def update_subchannel(channel_id: str, subchannel_id: str, request: Request):
    """Update an existing sub-channel"""
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    
    return await subchannel_manager.update_subchannel(channel_id, subchannel_id, data)


@app.delete("/api/channels/{channel_id}/subchannels/{subchannel_id}")
async def delete_subchannel(channel_id: str, subchannel_id: str):
    """Delete a sub-channel"""
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    return await subchannel_manager.delete_subchannel(channel_id, subchannel_id)


@app.post("/api/channels/{channel_id}/subchannels/{subchannel_id}/content")
async def assign_content_to_subchannel(channel_id: str, subchannel_id: str, request: Request):
    """Assign content to a sub-channel"""
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    
    return await subchannel_manager.assign_content_to_subchannel(channel_id, subchannel_id, data)


@app.get("/api/channels/{channel_id}/subchannels/{subchannel_id}/content")
async def get_subchannel_content(
    channel_id: str, 
    subchannel_id: str,
    limit: Optional[int] = Query(None, description="Maximum number of items to return"),
    offset: Optional[int] = Query(None, description="Number of items to skip")
):
    """Get content within a sub-channel"""
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    return await subchannel_manager.get_subchannel_content(channel_id, subchannel_id, limit, offset)


@app.get("/api/channels/{channel_id}/subchannels/{subchannel_id}/current.jpg")
async def get_subchannel_current_image(
    channel_id: str, 
    subchannel_id: str,
    resolution: str = Query("800x600", description="Image resolution (e.g., '800x600')")
):
    """
    Serve the current image for a specific subchannel (e.g., gallery)
    
    Args:
        channel_id: Channel ID
        subchannel_id: Subchannel ID (e.g., gallery ID)
        resolution: Image resolution in format 'WIDTHxHEIGHT'
    
    Returns:
        Current image file for the specified subchannel
    """
    if not subchannel_manager:
        raise HTTPException(status_code=501, detail="Sub-channel functionality not available")
    
    try:
        # Get the current image path for this subchannel
        image_path = await subchannel_manager.get_subchannel_current_image_path(
            channel_id, subchannel_id, resolution
        )
        
        # Determine MIME type based on file extension
        from pathlib import Path
        file_extension = Path(image_path).suffix.lower()
        if file_extension in ['.jpg', '.jpeg']:
            media_type = "image/jpeg"
        elif file_extension == '.png':
            media_type = "image/png"
        elif file_extension == '.gif':
            media_type = "image/gif"
        elif file_extension == '.webp':
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"  # Default fallback
        
        # Return the file with correct headers for inline display
        return FileResponse(
            path=image_path,
            media_type=media_type,
            headers={
                "Content-Disposition": "inline",  # Display in browser, don't force download
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
                "X-Subchannel-ID": subchannel_id,  # Custom header for debugging
                "X-Resolution": resolution,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving subchannel current image: {str(e)}")


# =========================================================================
# REDIS DISTRIBUTION ENDPOINTS
# =========================================================================

# Import distribution service
try:
    from distribution_service import get_distribution_service, DistributionStatus
    from content_set_manager import get_content_set_manager
    DISTRIBUTION_AVAILABLE = True
except ImportError:
    DISTRIBUTION_AVAILABLE = False

# Pydantic models for distribution
class ContentClaimRequest(BaseModel):
    """Request model for content claims"""
    client_version: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None

class ContentClaimResponse(BaseModel):
    """Response model for content claims"""
    status: str
    content_id: Optional[str] = None
    assignment_id: Optional[str] = None
    lease_expires_in: Optional[int] = None
    method: Optional[str] = None
    error: Optional[str] = None

class AcknowledgmentRequest(BaseModel):
    """Request model for assignment acknowledgments"""
    assignment_id: str
    status: str  # "displayed", "error", "skipped", etc.
    details: Optional[Dict[str, Any]] = None

class DistributionModeUpdate(BaseModel):
    """Request model for updating scene distribution mode"""
    distribution_mode: str  # "MIRROR", "SEQUENTIAL", "RANDOM_UNIQUE"

@app.post("/api/displays/{display_id}/claim_content", response_model=ContentClaimResponse)
async def claim_content_for_display(
    display_id: str,
    claim_request: ContentClaimRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Claim next content for a display client
    
    This endpoint allows display clients to request their next content item
    based on the scene's distribution mode (MIRROR, SEQUENTIAL, RANDOM_UNIQUE).
    """
    if not DISTRIBUTION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Distribution service not available")
    
    # Get display client
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Check if display has assigned scene
    if not display_client.assigned_scene_id:
        raise HTTPException(status_code=400, detail="No scene assigned to this display")
    
    # Update display last seen
    display_client.last_seen = datetime.datetime.now()
    db.commit()
    
    # Get distribution service
    dist_service = get_distribution_service(manager, SessionLocal)
    
    try:
        # Claim content
        result = await dist_service.claim_next_content(
            display_client.assigned_scene_id, 
            display_id
        )
        
        # Broadcast content assignment event if successful
        if result.get("status") == "assigned" and result.get("content_id"):
            await manager.broadcast_content_assigned(
                content_id=result["content_id"],
                display_client_id=display_id,
                lease_data={
                    "assignment_id": result.get("assignment_id"),
                    "lease_expires_in": result.get("lease_expires_in"),
                    "method": result.get("method"),
                    "scene_id": display_client.assigned_scene_id
                }
            )
        
        return ContentClaimResponse(**result)
        
    except Exception as e:
        logger.error(f"Error claiming content for display {display_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Content claim failed: {str(e)}")

@app.post("/api/displays/{display_id}/acknowledge")
async def acknowledge_content_assignment(
    display_id: str,
    ack_request: AcknowledgmentRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Acknowledge content assignment completion
    
    Display clients use this endpoint to report completion of content assignments,
    allowing the system to track performance and release leases.
    """
    if not DISTRIBUTION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Distribution service not available")
    
    # Get display client
    display_client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
    if not display_client:
        raise HTTPException(status_code=404, detail="Display client not found")
    
    # Check if display has assigned scene
    if not display_client.assigned_scene_id:
        raise HTTPException(status_code=400, detail="No scene assigned to this display")
    
    # Get distribution service
    dist_service = get_distribution_service(manager, SessionLocal)
    
    try:
        # Acknowledge assignment
        result = await dist_service.acknowledge_assignment(
            display_client.assigned_scene_id,
            display_id,
            ack_request.assignment_id,
            ack_request.status
        )
        
        # Broadcast content release event if assignment is completed
        if ack_request.status in ["displayed", "error", "skipped"]:
            # Try to get content_id from the assignment details
            content_id = result.get("content_id") or ack_request.details.get("content_id") if ack_request.details else None
            if content_id:
                await manager.broadcast_content_released(
                    content_id=content_id,
                    display_client_id=display_id,
                    reason=f"assignment_{ack_request.status}"
                )
        
        return result
        
    except Exception as e:
        logger.error(f"Error acknowledging assignment for display {display_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Acknowledgment failed: {str(e)}")

@app.put("/api/scenes/{scene_id}/distribution_mode")
async def update_scene_distribution_mode(
    scene_id: str,
    mode_update: DistributionModeUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Update distribution mode for a scene
    
    Changes how content is distributed to displays assigned to this scene:
    - MIRROR: All displays show the same content (default)
    - SEQUENTIAL: Displays cycle through content in order
    - RANDOM_UNIQUE: Displays get randomized content without duplication
    """
    # Get scene
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Validate distribution mode
    valid_modes = ["MIRROR", "SEQUENTIAL", "RANDOM_UNIQUE"]
    if mode_update.distribution_mode not in valid_modes:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid distribution mode. Must be one of: {', '.join(valid_modes)}"
        )
    
    # Update scene
    old_mode = scene.distribution_mode
    scene.distribution_mode = mode_update.distribution_mode
    db.commit()
    
    # If Redis is available, update Redis metadata
    if REDIS_AVAILABLE and DISTRIBUTION_AVAILABLE:
        try:
            redis_manager = get_redis_manager()
            if await redis_manager.is_healthy():
                meta_key = f"scene:{scene_id}:meta"
                metadata = await redis_manager.get_json(meta_key) or {}
                metadata.update({
                    "mode": mode_update.distribution_mode,
                    "last_updated": datetime.datetime.now().isoformat(),
                    "previous_mode": old_mode
                })
                await redis_manager.set_with_ttl(meta_key, metadata, 86400)  # 24 hour TTL
        except Exception as e:
            logger.warning(f"Failed to update Redis metadata for scene {scene_id}: {e}")
    
    # Broadcast mode change
    await broadcast_event("scene_distribution_mode_changed", {
        "scene_id": scene_id,
        "scene_name": scene.name,
        "old_mode": old_mode,
        "new_mode": mode_update.distribution_mode,
        "timestamp": datetime.datetime.now().isoformat()
    })
    
    return {
        "message": f"Distribution mode updated to {mode_update.distribution_mode}",
        "scene_id": scene_id,
        "old_mode": old_mode,
        "new_mode": mode_update.distribution_mode
    }

@app.get("/api/scenes/{scene_id}/distribution_status")
async def get_scene_distribution_status(
    scene_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Get current distribution status for a scene
    
    Returns information about active leases, queue status, and distribution metrics.
    """
    # Get scene
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    if not DISTRIBUTION_AVAILABLE:
        return {
            "scene_id": scene_id,
            "scene_name": scene.name,
            "distribution_mode": scene.distribution_mode,
            "distribution_available": False,
            "message": "Distribution service not available"
        }
    
    # Get distribution service
    dist_service = get_distribution_service(manager, SessionLocal)
    
    try:
        # Get Redis status
        redis_status = await dist_service.get_distribution_status(scene_id)
        
        # Add database information
        redis_status.update({
            "scene_name": scene.name,
            "db_distribution_mode": scene.distribution_mode,
            "distribution_available": True
        })
        
        return redis_status
        
    except Exception as e:
        logger.error(f"Error getting distribution status for scene {scene_id}: {e}")
        return {
            "scene_id": scene_id,
            "scene_name": scene.name,
            "distribution_mode": scene.distribution_mode,
            "distribution_available": True,
            "error": str(e)
        }

@app.get("/api/admin/distribution/overview")
async def get_distribution_overview(
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Get system-wide distribution overview
    
    Provides metrics and status for all scenes using distribution features.
    """
    if not DISTRIBUTION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Distribution service not available")
    
    try:
        # Get all scenes with distribution info
        scenes = db.query(Scene).all()
        
        overview = {
            "total_scenes": len(scenes),
            "redis_available": REDIS_AVAILABLE,
            "distribution_available": DISTRIBUTION_AVAILABLE,
            "scenes_by_mode": {
                "MIRROR": 0,
                "SEQUENTIAL": 0,
                "RANDOM_UNIQUE": 0
            },
            "scene_details": [],
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Count scenes by distribution mode
        for scene in scenes:
            mode = scene.distribution_mode or "MIRROR"
            overview["scenes_by_mode"][mode] += 1
            
            scene_info = {
                "id": scene.id,
                "name": scene.name,
                "distribution_mode": mode,
                "is_active": scene.is_active
            }
            
            # Get Redis status if available
            if REDIS_AVAILABLE:
                try:
                    dist_service = get_distribution_service(manager, SessionLocal)
                    redis_status = await dist_service.get_distribution_status(scene.id)
                    scene_info.update({
                        "active_leases": redis_status.get("active_leases", 0),
                        "queue_status": redis_status.get("queue_status", {})
                    })
                except Exception as e:
                    scene_info["redis_error"] = str(e)
            
            overview["scene_details"].append(scene_info)
        
        return overview
        
    except Exception as e:
        logger.error(f"Error getting distribution overview: {e}")
        raise HTTPException(status_code=500, detail=f"Overview failed: {str(e)}")

@app.post("/api/scenes/{scene_id}/refresh_content")
async def refresh_scene_content(
    scene_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Refresh content set for a scene from its channels
    
    Discovers content from all channels assigned to the scene and updates
    the Redis queues/bags for distribution.
    """
    # Get scene
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    if not scene.channels:
        raise HTTPException(status_code=400, detail="Scene has no channels assigned")
    
    if not DISTRIBUTION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Distribution service not available")
    
    try:
        # Get content set manager
        content_manager = get_content_set_manager(channel_discovery)
        
        # Update content set
        result = await content_manager.update_content_set(
            scene_id, 
            scene.channels, 
            force_update=force
        )
        
        # Get distribution service to check queue status
        dist_service = get_distribution_service(manager, SessionLocal)
        queue_stats = {}
        try:
            status = await dist_service.get_distribution_status(scene_id)
            queue_stats = status.get("queue_status", {})
        except Exception as e:
            logger.warning(f"Failed to get queue status for scene {scene_id}: {e}")
        
        # Broadcast content refresh event with queue stats
        await broadcast_event("scene_content_refreshed", {
            "scene_id": scene_id,
            "scene_name": scene.name,
            "status": result["status"],
            "item_count": result.get("item_count", 0),
            "epoch_id": result.get("epoch_id"),
            "force_refresh": force,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Broadcast queue status update
        if queue_stats:
            await manager.broadcast_queue_status(scene_id, queue_stats)
        
        # Broadcast new epoch started if epoch changed
        if result.get("epoch_id"):
            await manager.broadcast_epoch_started(
                scene_id=scene_id,
                epoch_number=int(result["epoch_id"]),
                distribution_stats={
                    "content_count": result.get("item_count", 0),
                    "distribution_mode": scene.distribution_mode,
                    "force_refresh": force
                }
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error refreshing content for scene {scene_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Content refresh failed: {str(e)}")

@app.get("/api/scenes/{scene_id}/content_info")
async def get_scene_content_info(
    scene_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Get detailed information about a scene's content set
    
    Returns content discovery info, Redis queue status, and metadata.
    """
    # Get scene
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    if not DISTRIBUTION_AVAILABLE:
        return {
            "scene_id": scene_id,
            "scene_name": scene.name,
            "distribution_available": False
        }
    
    try:
        # Get content set manager
        content_manager = get_content_set_manager(channel_discovery)
        
        # Get content info
        content_info = await content_manager.get_content_set_info(scene_id)
        
        # Add scene database info
        content_info.update({
            "scene_name": scene.name,
            "scene_channels": scene.channels or [],
            "distribution_mode": scene.distribution_mode,
            "scene_active": scene.is_active
        })
        
        return content_info
        
    except Exception as e:
        logger.error(f"Error getting content info for scene {scene_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Content info failed: {str(e)}")

@app.post("/api/scenes/{scene_id}/reset_distribution")
async def reset_scene_distribution(
    scene_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(check_rate_limit)
):
    """
    Reset distribution queues for a scene
    
    Clears current queues/bags and repopulates them from the content set.
    Useful for testing or when content gets stuck.
    """
    # Get scene
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    if not DISTRIBUTION_AVAILABLE:
        raise HTTPException(status_code=501, detail="Distribution service not available")
    
    try:
        # Get content set manager
        content_manager = get_content_set_manager(channel_discovery)
        
        # Reset distribution queues
        result = await content_manager.reset_distribution_queues(scene_id)
        
        # Broadcast reset event
        if result.get("status") == "reset":
            await broadcast_event("distribution_reset", {
                "scene_id": scene_id,
                "scene_name": scene.name,
                "distribution_mode": scene.distribution_mode,
                "epoch_id": result.get("epoch_id"),
                "content_items": result.get("content_items", 0),
                "timestamp": datetime.datetime.now().isoformat()
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error resetting distribution for scene {scene_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Distribution reset failed: {str(e)}")

@app.get("/api/admin/redis/status")
async def get_redis_admin_status(
    _: dict = Depends(check_rate_limit)
):
    """
    Get detailed Redis status for admin monitoring
    
    Provides comprehensive Redis health, memory usage, key counts, and performance metrics.
    """
    if not REDIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Redis not available")
    
    try:
        redis_manager = get_redis_manager()
        
        # Get basic health status
        health_status = await redis_manager.get_health_status()
        
        # Get key distribution info
        key_patterns = [
            "scene:*:meta",
            "scene:*:content_set", 
            "scene:*:content_items",
            "scene:*:sequential_queue",
            "scene:*:shuffle_bag",
            "scene:*:current_content",
            "lease:*",
            "completion:*"
        ]
        
        key_info = {}
        for pattern in key_patterns:
            try:
                info = await redis_manager.get_keys_info(pattern)
                key_info[pattern] = info
            except Exception as e:
                key_info[pattern] = {"error": str(e)}
        
        return {
            "health": health_status,
            "key_distribution": key_info,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting Redis admin status: {e}")
        raise HTTPException(status_code=500, detail=f"Redis status failed: {str(e)}")

@app.post("/api/admin/redis/cleanup")
async def cleanup_redis_data(
    expired_only: bool = True,
    _: dict = Depends(check_rate_limit)
):
    """
    Cleanup Redis data
    
    Removes expired keys and optionally cleans up test data.
    """
    if not REDIS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Redis not available")
    
    try:
        redis_manager = get_redis_manager()
        
        cleanup_stats = await redis_manager.cleanup_expired_keys()
        
        # If not expired_only, clean up test data
        if not expired_only:
            test_patterns = [
                "test:*",
                "completion:*",  # Old completion records
            ]
            
            for pattern in test_patterns:
                deleted = await redis_manager.delete_pattern(pattern)
                cleanup_stats[f"deleted_{pattern}"] = deleted
        
        return {
            "cleanup_completed": True,
            "stats": cleanup_stats,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during Redis cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# =========================================================================
# BACKGROUND TASKS: Distribution Performance Monitoring
# =========================================================================

import asyncio

async def distribution_monitoring_task():
    """Background task to monitor and broadcast distribution performance metrics"""
    while True:
        try:
            if DISTRIBUTION_AVAILABLE and REDIS_AVAILABLE:
                # Get all active scenes with distribution
                db = SessionLocal()
                try:
                    scenes = db.query(Scene).filter(Scene.is_active == True).all()
                    
                    for scene in scenes:
                        try:
                            # Get distribution service
                            dist_service = get_distribution_service(manager, SessionLocal)
                            
                            # Get current distribution status with error handling
                            try:
                                status = await dist_service.get_distribution_status(scene.id)
                                
                                # Extract performance metrics
                                performance_metrics = {
                                    "active_leases": status.get("active_leases", 0),
                                    "queue_size": status.get("queue_status", {}).get("total_items", 0),
                                    "assignments_last_minute": status.get("metrics", {}).get("assignments_last_minute", 0),
                                    "average_assignment_time": status.get("metrics", {}).get("avg_assignment_time", 0),
                                    "memory_usage": status.get("memory_usage", {}),
                                    "last_activity": status.get("last_activity")
                                }
                                
                                # Broadcast performance metrics
                                await manager.broadcast_distribution_performance(
                                    scene_id=scene.id,
                                    performance_metrics=performance_metrics
                                )
                                
                                # Broadcast queue status if it's changed significantly
                                queue_status = status.get("queue_status", {})
                                if queue_status:
                                    await manager.broadcast_queue_status(scene.id, queue_status)
                                    
                            except Exception as redis_error:
                                # Log Redis-related errors but don't crash the monitoring task
                                if "aioredis" in str(redis_error) or "get_async_client" in str(redis_error):
                                    logger.warning(f"Redis async client error for scene {scene.id} (using sync fallback): {redis_error}")
                                else:
                                    logger.error(f"Error monitoring scene {scene.id}: {redis_error}")
                                
                        except Exception as e:
                            logger.error(f"Error monitoring scene {scene.id}: {e}")
                            
                finally:
                    db.close()
                    
        except Exception as e:
            logger.error(f"Error in distribution monitoring task: {e}")
            
        # Wait 30 seconds before next monitoring cycle
        await asyncio.sleep(30)

# Start background monitoring task
@app.on_event("startup")
async def start_background_tasks():
    """Start background tasks when the application starts"""
    # Temporarily disable background monitoring until distribution service async client issues are resolved
    logger.info("Background distribution monitoring temporarily disabled due to async client compatibility")
    # if DISTRIBUTION_AVAILABLE and REDIS_AVAILABLE:
    #     asyncio.create_task(distribution_monitoring_task())
    #     logger.info("Started distribution monitoring background task")

# =========================================================================
