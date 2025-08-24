"""
Scene Service
Business logic for scene management operations
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.infrastructure.database.models import Scene


class SceneService:
    """Service class for scene operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_scenes(self) -> List[Dict[str, Any]]:
        """Get all scenes"""
        scenes = self.db.query(Scene).all()
        
        result = []
        for scene in scenes:
            result.append({
                "id": scene.id,
                "name": scene.name,
                "channels": scene.channels,
                "image_fit": scene.image_fit,
                "overlay": scene.overlay,
                "schedule": scene.schedule,
                "theme": scene.theme,
                "is_active": scene.is_active
            })
        
        return result
    
    def get_scene_by_id(self, scene_id: str) -> Optional[Scene]:
        """Get scene by ID"""
        return self.db.query(Scene).filter(Scene.id == scene_id).first()
    
    def create_scene(self, scene_data: Dict[str, Any]) -> Scene:
        """Create a new scene"""
        scene = Scene(
            id=scene_data["id"],
            name=scene_data["name"],
            channels=scene_data.get("channels", []),
            image_fit=scene_data.get("image_fit", "cover"),
            overlay=scene_data.get("overlay"),
            schedule=scene_data.get("schedule"),
            theme=scene_data.get("theme"),
            is_active=scene_data.get("is_active", False)
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
        if "image_fit" in scene_data:
            scene.image_fit = scene_data["image_fit"]
        if "overlay" in scene_data:
            scene.overlay = scene_data["overlay"]
        if "schedule" in scene_data:
            scene.schedule = scene_data["schedule"]
        if "theme" in scene_data:
            scene.theme = scene_data["theme"]
        if "is_active" in scene_data:
            scene.is_active = scene_data["is_active"]
        
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
