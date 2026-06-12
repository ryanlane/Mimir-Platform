"""
Distribution Service
Handles Redis integration, content distribution, and capability flags
"""
import asyncio
from enum import Enum
from typing import Any

from app.config import settings
from app.core.logging import get_logger

# Import metrics for instrumentation
try:
    from app.core.metrics import metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

logger = get_logger(__name__)


class DistributionMode(str, Enum):
    """Content distribution modes for multi-display systems"""
    MIRROR = "MIRROR"                    # All displays show the same content (default)
    SEQUENTIAL = "SEQUENTIAL"            # Displays cycle through content in order
    RANDOM_UNIQUE = "RANDOM_UNIQUE"      # Displays get randomized content without duplication


class DistributionService:
    """Service for managing content distribution across displays"""

    def __init__(self):
        self.redis_available = False
        self.redis_manager = None
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection if available"""
        try:
            # Try to import Redis manager
            if settings.redis_enabled:
                from redis_manager import get_redis_manager, init_redis
                init_redis()
                self.redis_manager = get_redis_manager()
                self.redis_available = True
                logger.info("Redis distribution enabled")
            else:
                logger.info("Redis distribution disabled by configuration")
        except ImportError:
            logger.warning("Redis manager not available - distribution features disabled")
            self.redis_available = False
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.redis_available = False

    def is_redis_available(self) -> bool:
        """Check if Redis distribution is available"""
        return self.redis_available and self.redis_manager is not None

    async def distribute_content(self, scene_id: str, content_data: dict[str, Any],
                               distribution_mode: DistributionMode = DistributionMode.MIRROR,
                               target_displays: list[str] | None = None) -> dict[str, Any]:
        """Distribute content to displays based on mode"""
        if not self.is_redis_available():
            logger.warning("Content distribution requested but Redis not available")
            # Record error metric
            if METRICS_AVAILABLE:
                metrics.distribution_error(scene_id, "distribute", "redis_unavailable")
            return {"status": "redis_unavailable", "distributed_to": []}

        try:
            distribution_result = await self._execute_distribution(
                scene_id, content_data, distribution_mode, target_displays
            )

            # Record successful distribution
            if METRICS_AVAILABLE and distribution_result.get("status") == "success":
                for display_id in distribution_result.get("distributed_to", []):
                    metrics.distribution_content_assigned(scene_id, display_id, content_data.get("content_id", "unknown"))

            logger.info(f"Content distributed for scene {scene_id}: {distribution_mode.value}")
            return distribution_result

        except Exception as e:
            logger.error(f"Distribution failed for scene {scene_id}: {e}")
            # Record error metric
            if METRICS_AVAILABLE:
                metrics.distribution_error(scene_id, "distribute", str(e))
            return {"status": "error", "error": str(e), "distributed_to": []}

    async def _execute_distribution(self, scene_id: str, content_data: dict[str, Any],
                                  distribution_mode: DistributionMode,
                                  target_displays: list[str] | None) -> dict[str, Any]:
        """Execute the actual content distribution"""
        distributed_to = []

        if distribution_mode == DistributionMode.MIRROR:
            # All displays get the same content
            distributed_to = await self._distribute_mirror(scene_id, content_data, target_displays)

        elif distribution_mode == DistributionMode.SEQUENTIAL:
            # Displays cycle through content in order
            distributed_to = await self._distribute_sequential(scene_id, content_data, target_displays)

        elif distribution_mode == DistributionMode.RANDOM_UNIQUE:
            # Displays get randomized unique content
            distributed_to = await self._distribute_random_unique(scene_id, content_data, target_displays)

        return {
            "status": "success",
            "distribution_mode": distribution_mode.value,
            "scene_id": scene_id,
            "distributed_to": distributed_to,
            "content_hash": content_data.get("hash"),
            "timestamp": content_data.get("timestamp")
        }

    async def _distribute_mirror(self, scene_id: str, content_data: dict[str, Any],
                                target_displays: list[str] | None) -> list[str]:
        """Distribute same content to all displays"""
        try:
            if target_displays:
                result = await self.redis_manager.distribute_to_displays(
                    scene_id, content_data, target_displays
                )
            else:
                result = await self.redis_manager.distribute_to_all_displays(
                    scene_id, content_data
                )
            return result.get("distributed_to", [])
        except Exception as e:
            logger.error(f"Mirror distribution failed: {e}")
            return []

    async def _distribute_sequential(self, scene_id: str, content_data: dict[str, Any],
                                   target_displays: list[str] | None) -> list[str]:
        """Distribute content sequentially to displays"""
        try:
            result = await self.redis_manager.distribute_sequential(
                scene_id, content_data, target_displays
            )
            return result.get("distributed_to", [])
        except Exception as e:
            logger.error(f"Sequential distribution failed: {e}")
            return []

    async def _distribute_random_unique(self, scene_id: str, content_data: dict[str, Any],
                                      target_displays: list[str] | None) -> list[str]:
        """Distribute unique randomized content to displays"""
        try:
            result = await self.redis_manager.distribute_random_unique(
                scene_id, content_data, target_displays
            )
            return result.get("distributed_to", [])
        except Exception as e:
            logger.error(f"Random unique distribution failed: {e}")
            return []

    async def get_distribution_status(self, scene_id: str) -> dict[str, Any]:
        """Get current distribution status for scene"""
        if not self.is_redis_available():
            return {"status": "redis_unavailable"}

        try:
            status = await self.redis_manager.get_scene_distribution_status(scene_id)
            return status
        except Exception as e:
            logger.error(f"Failed to get distribution status for {scene_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def reset_distribution(self, scene_id: str) -> dict[str, Any]:
        """Reset distribution state for scene"""
        if not self.is_redis_available():
            return {"status": "redis_unavailable"}

        try:
            result = await self.redis_manager.reset_scene_distribution(scene_id)
            logger.info(f"Distribution reset for scene: {scene_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to reset distribution for {scene_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def update_distribution_mode(self, scene_id: str, mode: DistributionMode) -> dict[str, Any]:
        """Update distribution mode for scene"""
        if not self.is_redis_available():
            return {"status": "redis_unavailable"}

        try:
            result = await self.redis_manager.update_scene_distribution_mode(scene_id, mode.value)
            logger.info(f"Distribution mode updated for {scene_id}: {mode.value}")
            return result
        except Exception as e:
            logger.error(f"Failed to update distribution mode for {scene_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def get_distribution_overview(self) -> dict[str, Any]:
        """Get overview of all distribution states"""
        if not self.is_redis_available():
            return {
                "status": "redis_unavailable",
                "scenes": [],
                "total_scenes": 0,
                "active_distributions": 0
            }

        try:
            overview = await self.redis_manager.get_distribution_overview()
            return overview
        except Exception as e:
            logger.error(f"Failed to get distribution overview: {e}")
            return {
                "status": "error",
                "error": str(e),
                "scenes": [],
                "total_scenes": 0,
                "active_distributions": 0
            }

    async def monitor_distribution_performance(self) -> dict[str, Any]:
        """Monitor distribution performance metrics"""
        if not self.is_redis_available():
            return {"status": "redis_unavailable"}

        try:
            metrics = self.redis_manager.get_performance_metrics()
            return {
                "status": "success",
                "redis_available": True,
                "metrics": metrics,
                "timestamp": metrics.get("timestamp") if metrics else None
            }
        except Exception as e:
            logger.error(f"Failed to get distribution performance: {e}")
            return {"status": "error", "error": str(e)}

    def get_capability_flags(self) -> dict[str, bool]:
        """Get current capability flags for features"""
        return {
            "redis_distribution": self.redis_available,
            "content_claiming": True,  # Always available
            "websocket_support": True,  # Always available
            "multi_display": True,  # Always available
            "sequential_distribution": self.redis_available,
            "random_unique_distribution": self.redis_available,
            "distribution_monitoring": self.redis_available,
            "performance_metrics": self.redis_available
        }

    async def start_distribution_monitoring(self):
        """Start background distribution monitoring task"""
        if not self.is_redis_available():
            logger.info("Distribution monitoring not started - Redis unavailable")
            return

        logger.info("Starting distribution monitoring task")
        asyncio.create_task(self._distribution_monitoring_loop())

    async def _distribution_monitoring_loop(self):
        """Background task for monitoring distribution performance"""
        while self.is_redis_available():
            try:
                await asyncio.sleep(30)  # Monitor every 30 seconds

                metrics = await self.monitor_distribution_performance()
                if metrics.get("status") == "success":
                    # Log performance metrics or send to monitoring system
                    logger.debug(f"Distribution performance: {metrics.get('metrics', {})}")

            except asyncio.CancelledError:
                logger.info("Distribution monitoring task cancelled")
                break
            except Exception as e:
                logger.error(f"Distribution monitoring error: {e}")
                await asyncio.sleep(60)  # Wait longer on error


# Global service instance
distribution_service = DistributionService()
