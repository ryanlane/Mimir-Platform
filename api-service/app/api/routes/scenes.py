"""
Scene API Routes
FastAPI router for scene-related endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.dependencies import get_scene_service
from app.core.services.scene_service import SceneService
from app.db.base import SessionLocal
from app.db.models import DisplayClient
from app.schemas.scenes import (
    SceneResponse,
    SceneCreate,
    SceneUpdate,
    SceneListResponse,
    SceneActivation,
    ChannelAssignment,
    ScheduleConfig
)


router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("", response_model=SceneListResponse)
async def list_scenes(
    limit: int = 100,
    offset: int = 0,
    scene_service: SceneService = Depends(get_scene_service)
):
    """Get all scenes"""
    return scene_service.get_scenes(limit=limit, offset=offset)


@router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(
    scene_id: str,
    scene_service: SceneService = Depends(get_scene_service)
):
    """Get scene by ID"""
    scene = scene_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    return {
        "id": scene.id,
        "name": scene.name,
        "channels": scene.channels,
        "overlay": scene.overlays,  # Map 'overlays' column to 'overlay' for frontend
        "schedule": scene.timing_config,  # Map 'timing_config' column to 'schedule' for frontend
        "distribution_mode": scene.distribution_mode,  # New field
        "is_active": scene.is_active
    }


@router.post("")
async def create_scene(
    scene_data: Dict[str, Any],
    scene_service: SceneService = Depends(get_scene_service)
):
    """Create a new scene"""
    scene = scene_service.create_scene(scene_data)
    return {
        "id": scene.id,
        "name": scene.name,
        "channels": scene.channels,
        "overlay": scene.overlays,  # Map 'overlays' column to 'overlay' for frontend
        "schedule": scene.timing_config,  # Map 'timing_config' column to 'schedule' for frontend
        "distribution_mode": scene.distribution_mode,  # New field
        "is_active": scene.is_active
    }


@router.put("/{scene_id}")
async def update_scene(
    scene_id: str,
    scene_data: Dict[str, Any],
    scene_service: SceneService = Depends(get_scene_service)
):
    """Update scene by ID"""
    scene = scene_service.update_scene(scene_id, scene_data)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    return {
        "id": scene.id,
        "name": scene.name,
        "channels": scene.channels,
        "overlay": scene.overlays,  # Map 'overlays' column to 'overlay' for frontend
        "schedule": scene.timing_config,  # Map 'timing_config' column to 'schedule' for frontend
        "distribution_mode": scene.distribution_mode,  # New field
        "is_active": scene.is_active
    }


@router.delete("/{scene_id}")
async def delete_scene(
    scene_id: str,
    scene_service: SceneService = Depends(get_scene_service)
):
    """Delete scene by ID"""
    success = scene_service.delete_scene(scene_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    return {"message": "Scene deleted successfully"}


@router.post("/{scene_id}/activate")
async def activate_scene(
    scene_id: str,
    scene_service: SceneService = Depends(get_scene_service)
):
    """Activate a scene"""
    success = scene_service.activate_scene(scene_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    return {"message": "Scene activated successfully"}


@router.get("/{scene_id}/displays")
async def get_scene_displays(
    scene_id: str,
    scene_service: SceneService = Depends(get_scene_service)
):
    """Get displays assigned to a specific scene"""
    # Check if scene exists
    scene = scene_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Get displays assigned to this scene
    db = SessionLocal()
    try:
        assigned_displays = db.query(DisplayClient).filter(
            DisplayClient.assigned_scene_id == scene_id
        ).all()
        
        display_list = []
        online_count = 0
        for display in assigned_displays:
            if display.is_online:
                online_count += 1
            
            display_list.append({
                "id": display.id,
                "name": display.name,
                "location": display.location,
                "is_online": display.is_online,
                "last_seen": display.last_seen,
                "display_type": display.display_type,
                "resolution": f"{display.width}x{display.height}" if display.width and display.height else "Unknown",
                "orientation": display.orientation
            })
        
        return {
            "scene_id": scene_id,
            "scene_name": scene.name,
            "display_stats": {
                "total_assigned": len(assigned_displays),
                "online_displays": online_count,
                "offline_displays": len(assigned_displays) - online_count
            },
            "assigned_displays": display_list
        }
    finally:
        db.close()
