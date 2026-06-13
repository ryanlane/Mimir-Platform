"""
Display-Scene Relationship Service
Enhanced service for managing the relationship between displays and scenes
Handles both registered displays (database) and discovered displays (in-memory)
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import DisplayClient, Scene
from app.services.discovered_display_manager import discovered_assignment_manager
from app.services.mdns_discovery import mdns_discovery_service


class DisplaySceneService:
    """Service for managing display-scene relationships"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = get_logger("display_scene_service")

    def assign_scene_to_display(
        self,
        display_id: str,
        scene_id: str,
        override_settings: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Assign a scene to either a registered or discovered display"""

        # Validate scene exists
        scene = self.db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")

        # Check if this is a registered display first
        display = self.db.query(DisplayClient).filter(DisplayClient.id == display_id).first()

        if display:
            # Handle registered display (database assignment)
            previous_scene_id = display.assigned_scene_id
            display.assigned_scene_id = scene_id
            display.last_seen = datetime.now()

            self.db.commit()
            self.db.refresh(display)

            self.logger.info(f"Assigned scene {scene_id} to registered display {display_id}")

            return {
                "display_id": display_id,
                "display_name": display.name,
                "display_type": "registered",
                "scene_id": scene_id,
                "scene_name": scene.name,
                "previous_scene_id": previous_scene_id,
                "assigned_at": datetime.now(),
                "success": True
            }
        else:
            # Check if this is a discovered display
            discovered_displays = mdns_discovery_service.get_discovered_displays()
            discovered_display = next((d for d in discovered_displays if d.display_id == display_id), None)

            if discovered_display:
                # Handle discovered display (in-memory assignment)
                previous_scene_id = discovered_assignment_manager.get_assigned_scene(display_id)
                success = discovered_assignment_manager.assign_scene(display_id, scene_id)

                if not success:
                    raise ValueError(f"Failed to assign scene to discovered display {display_id}")

                self.logger.info(f"Assigned scene {scene_id} to discovered display {display_id}")

                return {
                    "display_id": display_id,
                    "display_name": discovered_display.display_name,
                    "display_type": "discovered",
                    "scene_id": scene_id,
                    "scene_name": scene.name,
                    "previous_scene_id": previous_scene_id,
                    "assigned_at": datetime.now(),
                    "success": True
                }
            else:
                raise ValueError(f"Display {display_id} not found (neither registered nor discovered)")

    def unassign_scene_from_display(self, display_id: str) -> dict[str, Any]:
        """Remove scene assignment from either a registered or discovered display"""

        # Check if this is a registered display first
        display = self.db.query(DisplayClient).filter(DisplayClient.id == display_id).first()

        if display:
            # Handle registered display
            previous_scene_id = display.assigned_scene_id
            display.assigned_scene_id = None
            display.last_seen = datetime.now()

            self.db.commit()

            self.logger.info(f"Unassigned scene from registered display {display_id}")

            return {
                "display_id": display_id,
                "display_name": display.name,
                "display_type": "registered",
                "previous_scene_id": previous_scene_id,
                "unassigned_at": datetime.now(),
                "success": True
            }
        else:
            # Check if this is a discovered display
            discovered_displays = mdns_discovery_service.get_discovered_displays()
            discovered_display = next((d for d in discovered_displays if d.display_id == display_id), None)

            if discovered_display:
                # Handle discovered display
                previous_scene_id = discovered_assignment_manager.unassign_scene(display_id)

                self.logger.info(f"Unassigned scene from discovered display {display_id}")

                return {
                    "display_id": display_id,
                    "display_name": discovered_display.display_name,
                    "display_type": "discovered",
                    "previous_scene_id": previous_scene_id,
                    "unassigned_at": datetime.now(),
                    "success": True
                }
            else:
                raise ValueError(f"Display {display_id} not found (neither registered nor discovered)")

    def get_scene_with_display_stats(self, scene_id: str) -> dict[str, Any] | None:
        """Get scene information with display assignment statistics (both registered and discovered)"""

        scene = self.db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            return None

        # Get registered displays assigned to this scene
        registered_displays = self.db.query(DisplayClient).filter(
            DisplayClient.assigned_scene_id == scene_id
        ).all()

        # Get discovered displays assigned to this scene
        discovered_display_ids = discovered_assignment_manager.get_displays_for_scene(scene_id)
        discovered_displays = []

        if discovered_display_ids:
            all_discovered = mdns_discovery_service.get_discovered_displays()
            discovered_displays = [
                d for d in all_discovered
                if d.display_id in discovered_display_ids
            ]

        # Calculate statistics for both types
        registered_online = sum(1 for d in registered_displays if d.is_online)
        discovered_online = sum(1 for d in discovered_displays if d.is_online)

        total_assigned = len(registered_displays) + len(discovered_displays)
        total_online = registered_online + discovered_online
        total_offline = total_assigned - total_online

        # Build combined display list
        display_list = []

        # Add registered displays
        for display in registered_displays:
            display_list.append({
                "display_id": display.id,
                "display_name": display.name,
                "display_type": "registered",
                "location": display.location,
                "is_online": display.is_online,
                "last_seen": display.last_seen,
                "assigned_at": display.last_seen,  # Approximate
                "content_hash": display.current_content_hash
            })

        # Add discovered displays
        for discovered in discovered_displays:
            assignment_info = discovered_assignment_manager.get_assignment_info(discovered.display_id)
            display_list.append({
                "display_id": discovered.display_id,
                "display_name": discovered.display_name,
                "display_type": "discovered",
                "location": discovered.location,
                "is_online": discovered.is_online,
                "last_seen": discovered.last_seen,
                "assigned_at": assignment_info.get("assigned_at") if assignment_info else None,
                "content_hash": None  # Discovered displays don't store content hash
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
                "online_displays": total_online,
                "offline_displays": total_offline,
                "registered_displays": {
                    "total": len(registered_displays),
                    "online": registered_online,
                    "offline": len(registered_displays) - registered_online
                },
                "discovered_displays": {
                    "total": len(discovered_displays),
                    "online": discovered_online,
                    "offline": len(discovered_displays) - discovered_online
                },
                "last_updated": datetime.now()
            },
            "assigned_displays": display_list,
            "created_at": scene.created_at,
            "updated_at": scene.updated_at
        }

    def get_all_scenes_with_display_counts(self) -> list[dict[str, Any]]:
        """Get all scenes with their display assignment counts"""

        # Query scenes with display counts using a subquery
        # NOTE: Previous implementation used func.cast(..., 'integer') which passed a plain string
        # type name. Some SQLAlchemy versions attempt to access internal attributes on the type
        # object (e.g. _isnull) leading to AttributeError when given a raw string. Use the
        # sqlalchemy.cast helper with Integer type instead for portable numeric aggregation.
        scene_display_counts = (
            self.db.query(
                Scene.id,
                Scene.name,
                Scene.is_active,
                Scene.distribution_mode,
                Scene.created_at,
                Scene.updated_at,
                func.count(DisplayClient.id).label('display_count'),
                func.coalesce(func.sum(cast(DisplayClient.is_online, Integer)), 0).label('online_count'),
            )
            .outerjoin(DisplayClient, Scene.id == DisplayClient.assigned_scene_id)
            .group_by(Scene.id)
            .all()
        )

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
        display_ids: list[str],
        scene_id: str,
        override_previous: bool = True
    ) -> dict[str, Any]:
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

    def get_displays_by_location(self) -> list[dict[str, Any]]:
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

    def get_unassigned_displays(self) -> dict[str, list[dict[str, Any]]]:
        """Get displays that don't have scene assignments (both registered and discovered)"""

        # Get unassigned registered displays
        unassigned_registered = self.db.query(DisplayClient).filter(
            DisplayClient.assigned_scene_id.is_(None)
        ).all()

        registered_list = [
            {
                "display_id": display.id,
                "display_name": display.name,
                "display_type": "registered",
                "location": display.location,
                "is_online": display.is_online,
                "last_seen": display.last_seen,
                "discovery_method": display.discovery_method,
                "auto_discovered": display.auto_discovered
            }
            for display in unassigned_registered
        ]

        # Get unassigned discovered displays
        all_discovered = mdns_discovery_service.get_discovered_displays()
        all_discovered_ids = [d.display_id for d in all_discovered]
        unassigned_discovered_ids = discovered_assignment_manager.get_unassigned_discovered_displays(all_discovered_ids)

        discovered_list = []
        for discovered in all_discovered:
            if discovered.display_id in unassigned_discovered_ids:
                discovered_list.append({
                    "display_id": discovered.display_id,
                    "display_name": discovered.display_name,
                    "display_type": "discovered",
                    "location": discovered.location,
                    "is_online": discovered.is_online,
                    "last_seen": discovered.last_seen,
                    "discovery_method": "mdns",
                    "auto_discovered": True,
                    "hostname": discovered.hostname,
                    "webhook_port": discovered.webhook_port
                })

        return {
            "registered": registered_list,
            "discovered": discovered_list,
            "totals": {
                "registered_unassigned": len(registered_list),
                "discovered_unassigned": len(discovered_list),
                "total_unassigned": len(registered_list) + len(discovered_list)
            }
        }

    def reassign_displays_from_scene(
        self,
        old_scene_id: str,
        new_scene_id: str
    ) -> dict[str, Any]:
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

    def cleanup_discovered_assignments(self) -> dict[str, Any]:
        """Clean up assignments for discovered displays that are no longer active"""

        # Get currently active discovered displays
        active_discovered = mdns_discovery_service.get_discovered_displays()
        active_ids = {d.display_id for d in active_discovered}

        # Clean up stale assignments
        removed_count = discovered_assignment_manager.cleanup_stale_assignments(active_ids)

        self.logger.info(f"Cleaned up {removed_count} stale discovered display assignments")

        return {
            "stale_assignments_removed": removed_count,
            "active_discovered_displays": len(active_ids),
            "cleanup_timestamp": datetime.now()
        }

    def get_assignment_overview(self) -> dict[str, Any]:
        """Get comprehensive overview of all display assignments"""

        # Get registered display assignments
        all_registered = self.db.query(DisplayClient).all()
        registered_assigned = sum(1 for d in all_registered if d.assigned_scene_id)
        registered_unassigned = len(all_registered) - registered_assigned

        # Get discovered display assignments
        discovered_stats = discovered_assignment_manager.get_assignment_stats()
        all_discovered = mdns_discovery_service.get_discovered_displays()
        discovered_total = len(all_discovered)
        discovered_assigned = discovered_stats["total_assignments"]
        discovered_unassigned = discovered_total - discovered_assigned

        return {
            "registered_displays": {
                "total": len(all_registered),
                "assigned": registered_assigned,
                "unassigned": registered_unassigned
            },
            "discovered_displays": {
                "total": discovered_total,
                "assigned": discovered_assigned,
                "unassigned": discovered_unassigned
            },
            "overall": {
                "total_displays": len(all_registered) + discovered_total,
                "total_assigned": registered_assigned + discovered_assigned,
                "total_unassigned": registered_unassigned + discovered_unassigned
            },
            "discovered_assignment_stats": discovered_stats,
            "last_updated": datetime.now()
        }
