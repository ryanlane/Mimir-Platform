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
Scene Service
Business logic for scene management operations
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Scene, SchedulerJob, SchedulerJobSceneAssignment


class SceneService:
    """Service class for scene operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_scenes(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """Get all scenes with pagination support"""
        # Get total count
        total = self.db.query(Scene).count()

        # Get scenes with pagination
        scenes = self.db.query(Scene).offset(offset).limit(limit).all()

        scene_list = []
        for scene in scenes:
            refresh_schedule = self._derive_refresh_schedule(scene.id)
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
                "interrupt_sources": scene.interrupt_sources,
                "refresh_schedule": refresh_schedule,
                "created_at": scene.created_at,
                "updated_at": scene.updated_at
            })

        return {
            "scenes": scene_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    def get_scene_by_id(self, scene_id: str) -> Scene | None:
        """Get scene by ID"""
        return self.db.query(Scene).filter(Scene.id == scene_id).first()

    def get_scene_with_schedule(self, scene_id: str) -> dict[str, Any] | None:
        """Get a single scene serialized with refresh_schedule enrichment."""
        scene = self.get_scene_by_id(scene_id)
        if not scene:
            return None
        return {
            "id": scene.id,
            "name": scene.name,
            "channels": scene.channels,
            "overlay": scene.overlays,
            "schedule": scene.timing_config,
            "distribution_mode": scene.distribution_mode,
            "is_active": scene.is_active,
            "update_strategy": scene.update_strategy,
            "push_fallback_poll_seconds": scene.push_fallback_poll_seconds,
            "interrupt_sources": scene.interrupt_sources,
            "refresh_schedule": self._derive_refresh_schedule(scene.id),
            "created_at": scene.created_at,
            "updated_at": scene.updated_at,
        }

    def create_scene(self, scene_data: dict[str, Any]) -> Scene:
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
            push_fallback_poll_seconds=scene_data.get("push_fallback_poll_seconds"),
            interrupt_sources=scene_data.get("interrupt_sources"),
        )

        self.db.add(scene)
        self.db.commit()
        self.db.refresh(scene)
        return scene

    # ------------------- Internal helpers -------------------
    def _derive_refresh_schedule(self, scene_id: str) -> dict[str, Any] | None:
        """Find the enabled scheduler job with the smallest approx interval assigning this scene.

        Returns: {job_id, freq_unit, freq_value, enabled} or None
        """
        # Join assignments -> jobs
        assignment_rows = (
            self.db.query(SchedulerJobSceneAssignment, SchedulerJob)
            .filter(SchedulerJobSceneAssignment.scene_id == scene_id)
            .join(SchedulerJob, SchedulerJob.id == SchedulerJobSceneAssignment.job_id)
            .filter(SchedulerJob.enabled == True)  # noqa: E712
            .all()
        )
        if not assignment_rows:
            return None
        # Choose job with smallest approx_interval_seconds (fallback to freq_value)
        def _interval_key(row):
            assignment, job = row
            return job.approx_interval_seconds or (job.freq_value * _unit_seconds(job.freq_unit))

        best_assignment, best_job = min(assignment_rows, key=_interval_key)
        return {
            "job_id": best_job.id,
            "freq_unit": best_job.freq_unit,
            "freq_value": best_job.freq_value,
            "enabled": best_job.enabled,
        }

    def update_scene(self, scene_id: str, scene_data: dict[str, Any]) -> Scene | None:
        """Update scene by ID"""
        scene = self.get_scene_by_id(scene_id)
        if not scene:
            return None
        if "name" in scene_data:
            scene.name = scene_data["name"]
        if "channels" in scene_data:
            scene.channels = scene_data["channels"]
        if "overlay" in scene_data:
            scene.overlays = scene_data["overlay"]
        if "schedule" in scene_data:
            scene.timing_config = scene_data["schedule"]
        if "distribution_mode" in scene_data:
            scene.distribution_mode = scene_data["distribution_mode"]
        if "is_active" in scene_data:
            scene.is_active = scene_data["is_active"]
        if "update_strategy" in scene_data:
            scene.update_strategy = scene_data["update_strategy"]
        if "push_fallback_poll_seconds" in scene_data:
            scene.push_fallback_poll_seconds = scene_data["push_fallback_poll_seconds"]
        if "interrupt_sources" in scene_data:
            scene.interrupt_sources = scene_data["interrupt_sources"]
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
        self.db.query(Scene).update({"is_active": False})
        scene = self.get_scene_by_id(scene_id)
        if not scene:
            return False
        scene.is_active = True
        self.db.commit()
        return True

    def get_active_scene(self) -> Scene | None:
        """Get the currently active scene"""
        return self.db.query(Scene).filter(Scene.is_active == True).first()  # noqa: E712


def _unit_seconds(unit: str) -> int:
    mapping = {
        "minute": 60,
        "hour": 3600,
        "day": 86400,
        "week": 604800,
        "month": 2592000,  # Approx 30d
    }
    return mapping.get(unit, 60)
