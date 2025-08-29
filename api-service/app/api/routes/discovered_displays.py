"""
Enhanced Discovered Display API Routes
Endpoints specifically for managing discovered display assignments
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.db.base import SessionLocal
from app.core.services.display_scene_service import DisplaySceneService
from app.core.services.discovered_display_manager import discovered_assignment_manager
from app.services.mdns_discovery import mdns_discovery_service
from app.schemas.display_scene import (
    DisplaySceneAssignment,
    BulkSceneAssignment,
    BulkAssignmentResult
)


router = APIRouter(prefix="/discovered-displays", tags=["discovered-displays"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_display_scene_service(db: Session = Depends(get_db)) -> DisplaySceneService:
    """Get display-scene service instance"""
    return DisplaySceneService(db)


@router.get("/assignments")
async def get_discovered_display_assignments():
    """Get all current discovered display assignments"""
    try:
        assignments = discovered_assignment_manager.get_all_assignments()
        stats = discovered_assignment_manager.get_assignment_stats()
        
        return {
            "assignments": assignments,
            "stats": stats,
            "total_assignments": len(assignments)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assignments/{display_id}")
async def assign_scene_to_discovered_display(
    display_id: str,
    assignment: DisplaySceneAssignment,
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Assign scene to a discovered display"""
    try:
        # Verify this is actually a discovered display
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        discovered_display = next((d for d in discovered_displays if d.display_id == display_id), None)
        
        if not discovered_display:
            raise HTTPException(
                status_code=404, 
                detail=f"Discovered display {display_id} not found"
            )
        
        # Use the enhanced service which handles discovered displays
        result = service.assign_scene_to_display(
            display_id=display_id,
            scene_id=assignment.scene_id,
            override_settings=assignment.override_settings
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/assignments/{display_id}")
async def unassign_scene_from_discovered_display(
    display_id: str,
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Unassign scene from a discovered display"""
    try:
        result = service.unassign_scene_from_display(display_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assignments/bulk")
async def bulk_assign_discovered_displays(
    assignment: BulkSceneAssignment
):
    """Bulk assign scene to multiple discovered displays"""
    try:
        # Verify all displays are discovered displays
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        discovered_ids = {d.display_id for d in discovered_displays}
        
        invalid_ids = [did for did in assignment.display_ids if did not in discovered_ids]
        if invalid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"The following are not discovered displays: {invalid_ids}"
            )
        
        # Use the discovered assignment manager for bulk operations
        result = discovered_assignment_manager.bulk_assign_scene(
            display_ids=assignment.display_ids,
            scene_id=assignment.scene_id
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unassigned")
async def get_unassigned_discovered_displays():
    """Get discovered displays that don't have scene assignments"""
    try:
        all_discovered = mdns_discovery_service.get_discovered_displays()
        all_discovered_ids = [d.display_id for d in all_discovered]
        
        unassigned_ids = discovered_assignment_manager.get_unassigned_discovered_displays(all_discovered_ids)
        
        unassigned_displays = []
        for discovered in all_discovered:
            if discovered.display_id in unassigned_ids:
                unassigned_displays.append({
                    "display_id": discovered.display_id,
                    "display_name": discovered.display_name,
                    "location": discovered.location,
                    "hostname": discovered.hostname,
                    "is_online": discovered.is_online,
                    "last_seen": discovered.last_seen.isoformat(),
                    "discovered_at": discovered.discovered_at.isoformat(),
                    "webhook_port": discovered.webhook_port,
                    "resolution": discovered.resolution,
                    "client_version": discovered.client_version
                })
        
        return {
            "total_unassigned": len(unassigned_displays),
            "unassigned_displays": unassigned_displays
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scene/{scene_id}")
async def get_discovered_displays_for_scene(scene_id: str):
    """Get discovered displays assigned to a specific scene"""
    try:
        assigned_display_ids = discovered_assignment_manager.get_displays_for_scene(scene_id)
        
        if not assigned_display_ids:
            return {
                "scene_id": scene_id,
                "assigned_displays": [],
                "total_assigned": 0
            }
        
        # Get display details from mDNS service
        all_discovered = mdns_discovery_service.get_discovered_displays()
        assigned_displays = []
        
        for discovered in all_discovered:
            if discovered.display_id in assigned_display_ids:
                assignment_info = discovered_assignment_manager.get_assignment_info(discovered.display_id)
                assigned_displays.append({
                    "display_id": discovered.display_id,
                    "display_name": discovered.display_name,
                    "location": discovered.location,
                    "hostname": discovered.hostname,
                    "is_online": discovered.is_online,
                    "last_seen": discovered.last_seen.isoformat(),
                    "assigned_at": assignment_info.get("assigned_at") if assignment_info else None,
                    "webhook_port": discovered.webhook_port
                })
        
        return {
            "scene_id": scene_id,
            "assigned_displays": assigned_displays,
            "total_assigned": len(assigned_displays)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_stale_assignments(
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Clean up assignments for discovered displays that are no longer active"""
    try:
        result = service.cleanup_discovered_assignments()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_discovered_display_stats():
    """Get statistics about discovered display assignments"""
    try:
        assignment_stats = discovered_assignment_manager.get_assignment_stats()
        
        # Get additional context
        all_discovered = mdns_discovery_service.get_discovered_displays()
        online_count = sum(1 for d in all_discovered if d.is_online)
        
        return {
            "assignment_stats": assignment_stats,
            "discovery_stats": {
                "total_discovered": len(all_discovered),
                "online_discovered": online_count,
                "offline_discovered": len(all_discovered) - online_count
            },
            "last_updated": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/assignments")
async def clear_all_discovered_assignments():
    """Clear all discovered display assignments (for testing/reset)"""
    try:
        count = discovered_assignment_manager.clear_all_assignments()
        return {
            "message": f"Cleared {count} discovered display assignments",
            "cleared_count": count,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assignment/{display_id}")
async def get_discovered_display_assignment(display_id: str):
    """Get assignment information for a specific discovered display"""
    try:
        # Verify this is a discovered display
        discovered_displays = mdns_discovery_service.get_discovered_displays()
        discovered_display = next((d for d in discovered_displays if d.display_id == display_id), None)
        
        if not discovered_display:
            raise HTTPException(
                status_code=404,
                detail=f"Discovered display {display_id} not found"
            )
        
        assignment_info = discovered_assignment_manager.get_assignment_info(display_id)
        
        return {
            "display_id": display_id,
            "display_name": discovered_display.display_name,
            "location": discovered_display.location,
            "is_online": discovered_display.is_online,
            "assignment": assignment_info,
            "has_assignment": assignment_info is not None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
