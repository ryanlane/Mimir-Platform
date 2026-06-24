# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Scene API Routes
FastAPI router for scene-related endpoints
"""
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.db.base import SessionLocal
from app.db.models import DisplayClient
from app.dependencies import get_scene_service
from app.schemas.scenes import SceneListResponse, SceneResponse
from app.services.scene_refresh_service import scene_refresh_service
from app.services.scene_service import SceneService

router = APIRouter(prefix="/scenes", tags=["scenes"])


def _is_reachable_host(host: str | None) -> bool:
    return bool(host and settings._is_client_reachable_host(host))


def _extract_hostname(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate if "://" in candidate else f"http://{candidate}")
    return parsed.hostname or None


def _normalize_public_host_hint(candidate: str | None) -> str | None:
    host = _extract_hostname(candidate)
    return host if _is_reachable_host(host) else None


def _request_public_base_url(request: Request | None, public_host_hint: str | None = None) -> str | None:
    hint_host = _normalize_public_host_hint(public_host_hint)
    public_port = settings.public_port or settings.api_port
    if hint_host:
        suffix = "" if public_port in (None, 80, 443) else f":{public_port}"
        return f"http://{hint_host}{suffix}"

    if not request:
        return None

    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()
    host_header = (request.headers.get("host") or "").split(",", 1)[0].strip()
    authority = forwarded_host or host_header
    request_host = _extract_hostname(authority) or (request.url.hostname if request.url else None)
    if not _is_reachable_host(request_host):
        return None

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip()
    scheme = forwarded_proto or (request.url.scheme if request.url else "http")
    if authority:
        return f"{scheme}://{authority}".rstrip("/")

    port = request.url.port if request.url else None
    suffix = "" if port in (None, 80, 443) else f":{port}"
    return f"{scheme}://{request_host}{suffix}"


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
    scene_payload = scene_service.get_scene_with_schedule(scene_id)
    if not scene_payload:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene_payload


@router.post("")
async def create_scene(
    scene_data: dict[str, Any],
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
        "is_active": scene.is_active,
        "update_strategy": scene.update_strategy,
        "push_fallback_poll_seconds": scene.push_fallback_poll_seconds
    }


@router.put("/{scene_id}")
async def update_scene(
    scene_id: str,
    scene_data: dict[str, Any],
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
        "is_active": scene.is_active,
        "update_strategy": scene.update_strategy,
        "push_fallback_poll_seconds": scene.push_fallback_poll_seconds
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


@router.post("/{scene_id}/refresh_content")
async def refresh_scene_content(
    scene_id: str,
    scene_service: SceneService = Depends(get_scene_service)
):
    """
    Trigger a manual content refresh for a scene.
    This will request new images from all channels in the scene and distribute to assigned displays.
    """
    # Check if scene exists
    scene = scene_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        # Import here to avoid circular imports
        from app.services.scheduler_service import SchedulerService
        from app.services.scheduler_worker import SchedulerWorker

        # Create a temporary worker instance for manual execution
        worker = SchedulerWorker()

        # Create a database session for the scheduler service
        db = SessionLocal()
        try:
            scheduler_service = SchedulerService(db)  # noqa: F841 retained for potential future use

            # Create a mock assignment for the scene refresh
            from app.db.models import SchedulerJobSceneAssignment
            mock_assignment = SchedulerJobSceneAssignment(
                id=f"manual-{scene_id}",
                job_id="manual-refresh",
                scene_id=scene_id,
                refresh_method="content_refresh",
                priority=1
            )

            # Execute the scene refresh
            # Protected member used intentionally; consider refactor to public method in future
            result = await worker._refresh_single_scene(mock_assignment)  # noqa: SLF001

            return {
                "message": f"Content refresh triggered for scene {scene_id}",
                "scene_name": scene.name,
                "refresh_result": result,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            db.close()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh scene content: {str(e)}",
        ) from e


class SceneRefreshRequest(BaseModel):
    """Request body for targeted scene refresh operations."""
    target_devices: list[str] | None = Field(
        default=None,
        description="List of device IDs/hostnames to refresh; if omitted, refreshes all assigned displays",
        example=["livingroom-pi", "office-display-01"],
    )
    channel_subset: list[str] | None = Field(
        default=None,
        description="Optional subset of channel IDs to refresh; defaults to all channels in the scene",
    )
    force: bool = Field(
        default=False,
        description="Force refresh even if a previous refresh is currently in progress",
    )
    reason: str = Field(
        default="manual",
        description="Trigger reason label for logging and audit",
        example="manual-ui",
    )
    public_host_hint: str | None = Field(
        default=None,
        description="Optional LAN-reachable host or URL for generated media URLs.",
        example="192.168.1.28",
    )


@router.post("/{scene_id}/refresh")
async def refresh_scene_targeted(
    scene_id: str,
    req: SceneRefreshRequest,
    request: Request,
    scene_service: SceneService = Depends(get_scene_service),
):
    """Trigger a scene refresh, optionally targeting specific devices only.

    This endpoint uses the shared SceneRefreshService and supports selective device
    targeting to avoid refreshing all displays in a scene during manual updates.
    """
    # Validate scene exists early for a clearer 404
    scene = scene_service.get_scene_by_id(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        result = await scene_refresh_service.refresh_scene(
            scene_id,
            trigger_reason=req.reason or "manual",
            force=req.force,
            channel_subset=req.channel_subset,
            target_devices=req.target_devices,
            public_base_url_override=_request_public_base_url(request, req.public_host_hint),
        )
        return result.to_dict()
    except Exception as e:  # pragma: no cover - safety net to return 500s consistently
        raise HTTPException(status_code=500, detail=f"Failed to refresh scene: {e}") from e
