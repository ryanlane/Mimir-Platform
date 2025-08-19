from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime
import json

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
    db.commit()
    
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
            schedule=s.schedule
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
        schedule=scene.schedule
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
    
    db.delete(scene)
    db.commit()
    
    return {"message": f"Scene {scene_id} deleted successfully"}

@app.post("/api/scenes/{scene_id}/activate")
async def activate_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Deactivate all other scenes
    db.query(Scene).update({"is_active": False})
    
    # Activate this scene
    scene.is_active = True
    db.commit()
    
    return {"message": f"Scene {scene_id} activated successfully"}

@app.post("/api/scenes/{scene_id}/deactivate")
async def deactivate_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    scene.is_active = False
    db.commit()
    
    return {"message": f"Scene {scene_id} deactivated successfully"}

@app.post("/api/scenes/{scene_id}/display")
async def display_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
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
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
