"""
In-Memory Display Assignment Manager
Handles scene assignments for discovered displays that aren't stored in the database
"""
import threading
from datetime import datetime

from app.core.logging import get_logger


class DiscoveredDisplayAssignmentManager:
    """
    Manages scene assignments for discovered displays in memory.
    These assignments are ephemeral and reset when the API restarts.
    """

    def __init__(self):
        self.logger = get_logger("discovered_display_assignments")

        # In-memory storage for discovered display assignments
        self._assignments: dict[str, str] = {}  # display_id -> scene_id
        self._assignment_timestamps: dict[str, datetime] = {}  # display_id -> assignment_time
        self._lock = threading.RLock()  # Thread-safe access

        self.logger.info("Initialized in-memory assignment manager for discovered displays")

    def assign_scene(self, display_id: str, scene_id: str) -> bool:
        """
        Assign a scene to a discovered display.

        Args:
            display_id: The discovered display ID
            scene_id: The scene ID to assign

        Returns:
            bool: True if assignment was successful
        """
        with self._lock:
            try:
                old_scene = self._assignments.get(display_id)
                self._assignments[display_id] = scene_id
                self._assignment_timestamps[display_id] = datetime.now()

                if old_scene != scene_id:
                    self.logger.info(f"Assigned scene '{scene_id}' to discovered display '{display_id}' (was: {old_scene})")

                return True
            except Exception as e:
                self.logger.error(f"Failed to assign scene '{scene_id}' to discovered display '{display_id}': {e}")
                return False

    def unassign_scene(self, display_id: str) -> str | None:
        """
        Remove scene assignment from a discovered display.

        Args:
            display_id: The discovered display ID

        Returns:
            str: The previously assigned scene ID, or None if no assignment existed
        """
        with self._lock:
            old_scene = self._assignments.pop(display_id, None)
            self._assignment_timestamps.pop(display_id, None)

            if old_scene:
                self.logger.info(f"Unassigned scene '{old_scene}' from discovered display '{display_id}'")

            return old_scene

    def get_assigned_scene(self, display_id: str) -> str | None:
        """
        Get the scene assigned to a discovered display.

        Args:
            display_id: The discovered display ID

        Returns:
            str: The assigned scene ID, or None if no assignment exists
        """
        with self._lock:
            return self._assignments.get(display_id)

    def get_assignment_info(self, display_id: str) -> dict[str, str] | None:
        """
        Get detailed assignment information for a discovered display.

        Args:
            display_id: The discovered display ID

        Returns:
            dict: Assignment info including scene_id and timestamp, or None
        """
        with self._lock:
            scene_id = self._assignments.get(display_id)
            if scene_id:
                return {
                    "display_id": display_id,
                    "scene_id": scene_id,
                    "assigned_at": self._assignment_timestamps.get(display_id, datetime.now()).isoformat()
                }
            return None

    def get_displays_for_scene(self, scene_id: str) -> list[str]:
        """
        Get all discovered displays assigned to a specific scene.

        Args:
            scene_id: The scene ID

        Returns:
            list: List of discovered display IDs assigned to the scene
        """
        with self._lock:
            return [
                display_id for display_id, assigned_scene
                in self._assignments.items()
                if assigned_scene == scene_id
            ]

    def get_all_assignments(self) -> dict[str, dict[str, str]]:
        """
        Get all current discovered display assignments.

        Returns:
            dict: All assignments with detailed info
        """
        with self._lock:
            result = {}
            for display_id, scene_id in self._assignments.items():
                result[display_id] = {
                    "scene_id": scene_id,
                    "assigned_at": self._assignment_timestamps.get(display_id, datetime.now()).isoformat()
                }
            return result

    def get_unassigned_discovered_displays(self, all_discovered_display_ids: list[str]) -> list[str]:
        """
        Get discovered displays that don't have scene assignments.

        Args:
            all_discovered_display_ids: List of all discovered display IDs

        Returns:
            list: Display IDs that don't have scene assignments
        """
        with self._lock:
            assigned_ids = set(self._assignments.keys())
            return [
                display_id for display_id in all_discovered_display_ids
                if display_id not in assigned_ids
            ]

    def cleanup_stale_assignments(self, active_display_ids: set[str]) -> int:
        """
        Remove assignments for displays that are no longer discovered.

        Args:
            active_display_ids: Set of currently active discovered display IDs

        Returns:
            int: Number of stale assignments removed
        """
        with self._lock:
            stale_displays = []
            for display_id in self._assignments.keys():
                if display_id not in active_display_ids:
                    stale_displays.append(display_id)

            removed_count = 0
            for display_id in stale_displays:
                old_scene = self._assignments.pop(display_id, None)
                self._assignment_timestamps.pop(display_id, None)
                if old_scene:
                    removed_count += 1
                    self.logger.info(f"Cleaned up stale assignment: display '{display_id}' was assigned to scene '{old_scene}'")

            return removed_count

    def get_assignment_stats(self) -> dict[str, int]:
        """
        Get statistics about discovered display assignments.

        Returns:
            dict: Assignment statistics
        """
        with self._lock:
            # Count assignments per scene
            scene_counts = {}
            for scene_id in self._assignments.values():
                scene_counts[scene_id] = scene_counts.get(scene_id, 0) + 1

            return {
                "total_assignments": len(self._assignments),
                "unique_scenes": len(scene_counts),
                "assignments_per_scene": scene_counts
            }

    def bulk_assign_scene(self, display_ids: list[str], scene_id: str) -> dict[str, list[str]]:
        """
        Assign the same scene to multiple discovered displays.

        Args:
            display_ids: List of discovered display IDs
            scene_id: Scene ID to assign to all displays

        Returns:
            dict: Results with successful and failed assignments
        """
        successful = []
        failed = []

        with self._lock:
            for display_id in display_ids:
                try:
                    if self.assign_scene(display_id, scene_id):
                        successful.append(display_id)
                    else:
                        failed.append(display_id)
                except Exception as e:
                    self.logger.error(f"Bulk assignment failed for display '{display_id}': {e}")
                    failed.append(display_id)

        self.logger.info(f"Bulk assigned scene '{scene_id}' to {len(successful)}/{len(display_ids)} discovered displays")

        return {
            "successful": successful,
            "failed": failed,
            "total_processed": len(display_ids),
            "success_count": len(successful),
            "error_count": len(failed)
        }

    def clear_all_assignments(self) -> int:
        """
        Clear all discovered display assignments.
        Used for testing or emergency reset.

        Returns:
            int: Number of assignments cleared
        """
        with self._lock:
            count = len(self._assignments)
            self._assignments.clear()
            self._assignment_timestamps.clear()

            self.logger.warning(f"Cleared all {count} discovered display assignments")
            return count


# Global instance for the application
discovered_assignment_manager = DiscoveredDisplayAssignmentManager()
