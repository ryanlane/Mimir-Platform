"""
Scene Service
Business logic for scene management operations
"""
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models import Scene


class SceneService:
    """Service class for scene operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_scenes(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get all scenes with pagination support"""
        # Get total count
        total = self.db.query(Scene).count()
        
        # Get scenes with pagination
        scenes = self.db.query(Scene).offset(offset).limit(limit).all()
        
        scene_list = []
        for scene in scenes:
            scene_list.append({
                "id": scene.id,
                "name": scene.name,
                "channels": scene.channels,
                "overlay": scene.overlays,  # Map 'overlays' column to 'overlay' for frontend
                "schedule": scene.timing_config,  # Map 'timing_config' column to 'schedule' for frontend
                "distribution_mode": scene.distribution_mode,  # New field
                "is_active": scene.is_active,
                "update_strategy": scene.update_strategy,
                "push_fallback_poll_seconds": scene.push_fallback_poll_seconds,
                "created_at": scene.created_at,
                "updated_at": scene.updated_at
            })
        
        return {
            "scenes": scene_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    def get_scene_by_id(self, scene_id: str) -> Optional[Scene]:
        """Get scene by ID"""
        return self.db.query(Scene).filter(Scene.id == scene_id).first()
    
    def create_scene(self, scene_data: Dict[str, Any]) -> Scene:
        """Create a new scene"""
        # Generate a UUID for the new scene if not provided
        scene_id = scene_data.get("id") or str(uuid.uuid4())
        
        scene = Scene(
            id=scene_id,
            name=scene_data["name"],
            channels=scene_data.get("channels", []),
            overlays=scene_data.get("overlay"),  # Map 'overlay' to 'overlays' column
            timing_config=scene_data.get("schedule"),  # Map 'schedule' to 'timing_config' column
            distribution_mode=scene_data.get("distribution_mode", "MIRROR"),  # New field
            is_active=scene_data.get("is_active", False),
            update_strategy=scene_data.get("update_strategy", "scheduler"),
            push_fallback_poll_seconds=scene_data.get("push_fallback_poll_seconds")
        )
        
        self.db.add(scene)
        self.db.commit()
        self.db.refresh(scene)
        return scene
    
    def update_scene(self, scene_id: str, scene_data: Dict[str, Any]) -> Optional[Scene]:
        """Update scene by ID"""
        scene = self.get_scene_by_id(scene_id)
        if not scene:
            return None
        
        # Update scene attributes
        if "name" in scene_data:
            scene.name = scene_data["name"]
        if "channels" in scene_data:
            scene.channels = scene_data["channels"]
        if "overlay" in scene_data:
            scene.overlays = scene_data["overlay"]  # Map 'overlay' to 'overlays' column
        if "schedule" in scene_data:
            scene.timing_config = scene_data["schedule"]  # Map 'schedule' to 'timing_config' column
        if "distribution_mode" in scene_data:
            scene.distribution_mode = scene_data["distribution_mode"]  # New field
        if "is_active" in scene_data:
            scene.is_active = scene_data["is_active"]
        if "update_strategy" in scene_data:
            scene.update_strategy = scene_data["update_strategy"]
        if "push_fallback_poll_seconds" in scene_data:
            scene.push_fallback_poll_seconds = scene_data["push_fallback_poll_seconds"]
        
        self.db.commit()
        self.db.refresh(scene)
        return scene
    
    def delete_scene(self, scene_id: str) -> bool:
        """Delete scene by ID"""
        scene = self.get_scene_by_id(scene_id)
        if not scene:
            return False
        
        self.db.delete(scene)
        self.db.commit()
        return True
    
    def activate_scene(self, scene_id: str) -> bool:
        """Activate a scene and deactivate others"""
        # First deactivate all scenes
        self.db.query(Scene).update({"is_active": False})
        
        # Then activate the specified scene
        scene = self.get_scene_by_id(scene_id)
        if not scene:
            return False
        
        scene.is_active = True
        self.db.commit()
        return True
    
    def get_active_scene(self) -> Optional[Scene]:
        """Get the currently active scene"""
        return self.db.query(Scene).filter(Scene.is_active == True).first()
