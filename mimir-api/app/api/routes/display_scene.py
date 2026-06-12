"""
Display-Scene Analytics and Reporting API Routes
Endpoints for scene assignment analytics and reporting
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.services.display_scene_service import DisplaySceneService
from app.db.base import SessionLocal

router = APIRouter(prefix="/display-scene", tags=["display-scene"])

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

# ANALYTICS & REPORTING (the actually useful stuff)
@router.get("/scenes/with-displays")
async def get_scenes_with_display_stats(
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Get all scenes with display assignment statistics"""
    try:
        scenes = service.get_all_scenes_with_display_counts()
        return scenes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/scenes/{scene_id}/displays")
async def get_scene_with_displays(
    scene_id: str,
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Get detailed scene information including assigned displays"""
    try:
        scene_data = service.get_scene_with_display_stats(scene_id)
        if not scene_data:
            raise HTTPException(status_code=404, detail="Scene not found")
        return scene_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/displays/by-location")
async def get_displays_by_location(
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Get displays grouped by location with scene assignments"""
    try:
        location_groups = service.get_displays_by_location()
        return location_groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/dashboard/overview")
async def get_assignment_dashboard(
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Get overview dashboard data for display-scene assignments"""
    try:
        # Get scenes with display counts
        scenes_with_stats = service.get_all_scenes_with_display_counts()

        # Get unassigned displays
        unassigned_displays = service.get_unassigned_displays()

        # Get location-based grouping
        location_groups = service.get_displays_by_location()

        # Calculate summary statistics
        total_scenes = len(scenes_with_stats)
        total_assigned_displays = sum(scene["display_stats"]["total_assigned"] for scene in scenes_with_stats)
        total_online_displays = sum(scene["display_stats"]["online_displays"] for scene in scenes_with_stats)
        total_unassigned = len(unassigned_displays)

        return {
            "summary": {
                "total_scenes": total_scenes,
                "total_assigned_displays": total_assigned_displays,
                "total_online_displays": total_online_displays,
                "total_unassigned_displays": total_unassigned,
                "total_locations": len(location_groups),
                "last_updated": datetime.datetime.now()
            },
            "scenes_with_displays": scenes_with_stats[:10],  # Top 10 scenes
            "unassigned_displays": unassigned_displays,
            "location_groups": location_groups,
            "recommendations": [
                f"{total_unassigned} displays need scene assignments" if total_unassigned > 0 else None,
                f"{total_assigned_displays - total_online_displays} assigned displays are offline" if (total_assigned_displays - total_online_displays) > 0 else None,
                "Consider grouping displays by location for easier management" if len(location_groups) > 5 else None
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/assignments/status")
async def get_assignment_status(
    scene_id: str | None = Query(None, description="Filter by scene ID"),
    location: str | None = Query(None, description="Filter by location"),
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Get current assignment status with filtering options"""
    try:
        if scene_id:
            # Get specific scene's assignment status
            scene_data = service.get_scene_with_display_stats(scene_id)
            if not scene_data:
                raise HTTPException(status_code=404, detail="Scene not found")
            return scene_data

        elif location:
            # Get assignment status for a specific location
            location_groups = service.get_displays_by_location()
            matching_location = next((lg for lg in location_groups if lg["location"] == location), None)
            if not matching_location:
                raise HTTPException(status_code=404, detail="Location not found")
            return matching_location

        else:
            # Get overall assignment status
            scenes = service.get_all_scenes_with_display_counts()
            unassigned = service.get_unassigned_displays()

            return {
                "scenes": scenes,
                "unassigned_displays": unassigned,
                "total_assignments": sum(scene["display_stats"]["total_assigned"] for scene in scenes)
            }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/assignments/reassign")
async def reassign_displays_between_scenes(
    old_scene_id: str = Query(..., description="Source scene ID"),
    new_scene_id: str = Query(..., description="Target scene ID"),
    service: DisplaySceneService = Depends(get_display_scene_service)
):
    """Move all displays from one scene to another"""
    try:
        result = service.reassign_displays_from_scene(old_scene_id, new_scene_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

