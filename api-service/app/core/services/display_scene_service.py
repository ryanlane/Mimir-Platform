"""
Display-Scene Relationship Service
Enhanced service for managing the relationship between displays and scenes
"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
import uuid

from app.db.models import DisplayClient, Scene, ContentLease
from app.core.logging import get_logger


class DisplaySceneService:
    """Service for managing display-scene relationships"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = get_logger("display_scene_service")
    
    def assign_scene_to_display(
        self, 
        display_id: str, 
        scene_id: str, 
        override_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Assign a scene to a specific display"""
        
        # Validate display exists
        display = self.db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
        if not display:
            raise ValueError(f"Display {display_id} not found")
        
        # Validate scene exists
        scene = self.db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")
        
        # Store previous assignment for history
        previous_scene_id = display.assigned_scene_id
        
        # Update the assignment
        display.assigned_scene_id = scene_id
        display.last_seen = datetime.now()
        
        # Store override settings if provided (would require new column in future)
        # For now, we'll track this in content_hash as JSON if needed
        
        self.db.commit()
        self.db.refresh(display)
        
        self.logger.info(f"Assigned scene {scene_id} to display {display_id}")
        
        return {
            "display_id": display_id,
            "display_name": display.name,
            "scene_id": scene_id,
            "scene_name": scene.name,
            "previous_scene_id": previous_scene_id,
            "assigned_at": datetime.now(),
            "success": True
        }
    
    def unassign_scene_from_display(self, display_id: str) -> Dict[str, Any]:
        """Remove scene assignment from display"""
        
        display = self.db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
        if not display:
            raise ValueError(f"Display {display_id} not found")
        
        previous_scene_id = display.assigned_scene_id
        display.assigned_scene_id = None
        display.last_seen = datetime.now()
        
        self.db.commit()
        
        self.logger.info(f"Unassigned scene from display {display_id}")
        
        return {
            "display_id": display_id,
            "display_name": display.name,
            "previous_scene_id": previous_scene_id,
            "unassigned_at": datetime.now(),
            "success": True
        }
    
    def get_scene_with_display_stats(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Get scene information with display assignment statistics"""
        
        scene = self.db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            return None
        
        # Get all displays assigned to this scene
        assigned_displays = self.db.query(DisplayClient).filter(
            DisplayClient.assigned_scene_id == scene_id
        ).all()
        
        # Calculate statistics
        total_assigned = len(assigned_displays)
        online_displays = sum(1 for d in assigned_displays if d.is_online)
        offline_displays = total_assigned - online_displays
        
        # Build display list
        display_list = []
        for display in assigned_displays:
            display_list.append({
                "display_id": display.id,
                "display_name": display.name,
                "location": display.location,
                "is_online": display.is_online,
                "last_seen": display.last_seen,
                "assigned_at": display.last_seen,  # Approximate, would need proper tracking
                "content_hash": display.current_content_hash
            })
        
        return {
            "id": scene.id,
            "name": scene.name,
            "channels": scene.channels,
            "overlay": scene.overlays,
            "schedule": scene.timing_config,
            "distribution_mode": scene.distribution_mode,
            "is_active": scene.is_active,
            "display_stats": {
                "total_assigned": total_assigned,
                "online_displays": online_displays,
                "offline_displays": offline_displays,
                "last_updated": datetime.now()
            },
            "assigned_displays": display_list,
            "created_at": scene.created_at,
            "updated_at": scene.updated_at
        }
    
    def get_all_scenes_with_display_counts(self) -> List[Dict[str, Any]]:
        """Get all scenes with their display assignment counts"""
        
        # Query scenes with display counts using a subquery
        scene_display_counts = self.db.query(
            Scene.id,
            Scene.name,
            Scene.is_active,
            Scene.distribution_mode,
            Scene.created_at,
            Scene.updated_at,
            func.count(DisplayClient.id).label('display_count'),
            func.sum(func.cast(DisplayClient.is_online, 'integer')).label('online_count')
        ).outerjoin(
            DisplayClient, Scene.id == DisplayClient.assigned_scene_id
        ).group_by(Scene.id).all()
        
        scenes_with_stats = []
        for result in scene_display_counts:
            display_count = result.display_count or 0
            online_count = result.online_count or 0
            offline_count = display_count - online_count
            
            scenes_with_stats.append({
                "id": result.id,
                "name": result.name,
                "is_active": result.is_active,
                "distribution_mode": result.distribution_mode,
                "display_stats": {
                    "total_assigned": display_count,
                    "online_displays": online_count,
                    "offline_displays": offline_count,
                    "last_updated": datetime.now()
                },
                "created_at": result.created_at,
                "updated_at": result.updated_at
            })
        
        return scenes_with_stats
    
    def bulk_assign_scene(
        self, 
        display_ids: List[str], 
        scene_id: str, 
        override_previous: bool = True
    ) -> Dict[str, Any]:
        """Assign the same scene to multiple displays"""
        
        # Validate scene exists
        scene = self.db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")
        
        successful_assignments = []
        failed_assignments = []
        
        for display_id in display_ids:
            try:
                display = self.db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
                if not display:
                    failed_assignments.append({
                        "display_id": display_id,
                        "error": "Display not found"
                    })
                    continue
                
                # Check if override is needed
                if not override_previous and display.assigned_scene_id:
                    failed_assignments.append({
                        "display_id": display_id,
                        "error": f"Display already assigned to scene {display.assigned_scene_id}"
                    })
                    continue
                
                display.assigned_scene_id = scene_id
                display.last_seen = datetime.now()
                successful_assignments.append(display_id)
                
            except Exception as e:
                failed_assignments.append({
                    "display_id": display_id,
                    "error": str(e)
                })
        
        self.db.commit()
        
        self.logger.info(f"Bulk assigned scene {scene_id} to {len(successful_assignments)} displays")
        
        return {
            "successful_assignments": successful_assignments,
            "failed_assignments": failed_assignments,
            "total_processed": len(display_ids),
            "success_count": len(successful_assignments),
            "error_count": len(failed_assignments),
            "scene_id": scene_id,
            "scene_name": scene.name
        }
    
    def get_displays_by_location(self) -> List[Dict[str, Any]]:
        """Group displays by location for easier management"""
        
        # Get all displays with their assigned scenes
        displays_with_scenes = self.db.query(DisplayClient, Scene).outerjoin(
            Scene, DisplayClient.assigned_scene_id == Scene.id
        ).all()
        
        # Group by location
        location_groups = {}
        for display, scene in displays_with_scenes:
            location = display.location or "Unknown Location"
            
            if location not in location_groups:
                location_groups[location] = {
                    "location": location,
                    "displays": [],
                    "scene_assignments": {}
                }
            
            display_info = {
                "display_id": display.id,
                "display_name": display.name,
                "is_online": display.is_online,
                "assigned_scene_id": display.assigned_scene_id,
                "assigned_scene_name": scene.name if scene else None,
                "last_seen": display.last_seen
            }
            
            location_groups[location]["displays"].append(display_info)
            
            # Track scene assignments per location
            if display.assigned_scene_id:
                scene_id = display.assigned_scene_id
                if scene_id not in location_groups[location]["scene_assignments"]:
                    location_groups[location]["scene_assignments"][scene_id] = 0
                location_groups[location]["scene_assignments"][scene_id] += 1
        
        # Convert to list and add summary info
        result = []
        for location_data in location_groups.values():
            # Determine dominant scene for location
            assignments = location_data["scene_assignments"]
            dominant_scene = max(assignments.keys(), key=assignments.get) if assignments else None
            
            result.append({
                "location": location_data["location"],
                "display_count": len(location_data["displays"]),
                "displays": location_data["displays"],
                "dominant_scene": dominant_scene,
                "scene_distribution": assignments
            })
        
        return sorted(result, key=lambda x: x["display_count"], reverse=True)
    
    def get_unassigned_displays(self) -> List[Dict[str, Any]]:
        """Get displays that don't have scene assignments"""
        
        unassigned_displays = self.db.query(DisplayClient).filter(
            DisplayClient.assigned_scene_id.is_(None)
        ).all()
        
        return [
            {
                "display_id": display.id,
                "display_name": display.name,
                "location": display.location,
                "is_online": display.is_online,
                "last_seen": display.last_seen,
                "discovery_method": display.discovery_method,
                "auto_discovered": display.auto_discovered
            }
            for display in unassigned_displays
        ]
    
    def reassign_displays_from_scene(
        self, 
        old_scene_id: str, 
        new_scene_id: str
    ) -> Dict[str, Any]:
        """Move all displays from one scene to another"""
        
        # Validate both scenes exist
        old_scene = self.db.query(Scene).filter(Scene.id == old_scene_id).first()
        new_scene = self.db.query(Scene).filter(Scene.id == new_scene_id).first()
        
        if not old_scene:
            raise ValueError(f"Source scene {old_scene_id} not found")
        if not new_scene:
            raise ValueError(f"Target scene {new_scene_id} not found")
        
        # Find all displays assigned to old scene
        affected_displays = self.db.query(DisplayClient).filter(
            DisplayClient.assigned_scene_id == old_scene_id
        ).all()
        
        # Update assignments
        count = 0
        for display in affected_displays:
            display.assigned_scene_id = new_scene_id
            display.last_seen = datetime.now()
            count += 1
        
        self.db.commit()
        
        self.logger.info(f"Reassigned {count} displays from scene {old_scene_id} to {new_scene_id}")
        
        return {
            "old_scene_id": old_scene_id,
            "new_scene_id": new_scene_id,
            "displays_moved": count,
            "affected_display_ids": [d.id for d in affected_displays],
            "success": True
        }
