"""
Scene API Routes
FastAPI router for scene-related endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from app.dependencies import get_scene_service
from app.core.services.scene_service import SceneService


router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("")
async def list_scenes(
    scene_service: SceneService = Depends(get_scene_service)
):
    """Get all scenes"""
    return scene_service.get_scenes()


@router.get("/{scene_id}")
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
        "image_fit": scene.image_fit,
        "overlay": scene.overlay,
        "schedule": scene.schedule,
        "theme": scene.theme,
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
        "image_fit": scene.image_fit,
        "overlay": scene.overlay,
        "schedule": scene.schedule,
        "theme": scene.theme,
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
        "image_fit": scene.image_fit,
        "overlay": scene.overlay,
        "schedule": scene.schedule,
        "theme": scene.theme,
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
