"""
Distribution Service for Mimir Platform

This module handles content distribution across multiple displays using Redis
for fast operations and SQL fallback for reliability.
"""

import json
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

# Import Redis manager (with fallback handling)
try:
    from redis_manager import RedisManager, get_redis_manager
    from content_set_manager import get_content_set_manager
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

class DistributionStatus(str, Enum):
    """Status values for content distribution operations"""
    ASSIGNED = "assigned"
    EXISTING_LEASE = "existing_lease"
    QUEUE_EMPTY = "queue_empty"
    LEASE_NOT_FOUND = "lease_not_found"
    ACKNOWLEDGED = "acknowledged"
    ERROR = "error"

class DistributionService:
    """
    Core distribution service that handles content assignment across displays
    using Redis for performance with SQL fallback for reliability.
    """
    
    def __init__(self, websocket_manager=None, db_session_factory=None):
        """
        Initialize distribution service
        
        Args:
            websocket_manager: WebSocket manager for real-time notifications
            db_session_factory: Database session factory for SQL fallback
        """
        self.ws_manager = websocket_manager
        self.db_session_factory = db_session_factory
        self.redis_available = REDIS_AVAILABLE
        self.redis_manager = None
        self.content_manager = None
        
        # Initialize Redis connection if available
        if REDIS_AVAILABLE:
            try:
                self.redis_manager = get_redis_manager()
                self.content_manager = get_content_set_manager()
            except Exception as e:
                logger.warning(f"Redis initialization failed: {e}")
                self.redis_available = False
    
    async def is_redis_healthy(self) -> bool:
        """Check if Redis is available and healthy"""
        if not self.redis_available or not self.redis_manager:
            return False
        
        try:
            return await self.redis_manager.is_healthy()
        except Exception:
            return False
    
    async def claim_next_content(self, scene_id: str, display_id: str) -> Dict[str, Any]:
        """
        Claim next content item for a display
        
        Args:
            scene_id: Scene identifier
            display_id: Display client identifier
            
        Returns:
            Dict with status, content_id, lease information, and metadata
        """
        try:
            # Try Redis first if available
            if await self.is_redis_healthy():
                return await self._claim_via_redis(scene_id, display_id)
            else:
                logger.info(f"Redis unavailable, using SQL fallback for {display_id}")
                return await self._claim_via_sql(scene_id, display_id)
                
        except Exception as e:
            logger.error(f"Error claiming content for display {display_id}: {e}")
            return {
                "status": DistributionStatus.ERROR,
                "error": str(e),
                "method": "error"
            }
    
    async def _claim_via_redis(self, scene_id: str, display_id: str) -> Dict[str, Any]:
        """Claim content using Redis operations"""
        
        # Check for existing lease first
        lease_key = f"lease:{scene_id}:{display_id}"
        existing_lease = await self.redis_manager.get_json(lease_key)
        
        if existing_lease:
            # Get TTL for existing lease
            client = await self.redis_manager.get_async_client()
            ttl = await client.ttl(lease_key)
            
            return {
                "status": DistributionStatus.EXISTING_LEASE,
                "content_id": existing_lease["content_id"],
                "lease_expires_in": ttl,
                "assignment_id": existing_lease.get("assignment_id"),
                "method": "redis"
            }
        
        # Get scene distribution mode and metadata
        scene_meta_key = f"scene:{scene_id}:meta"
        scene_meta = await self._get_scene_metadata(scene_id)
        
        distribution_mode = scene_meta.get("mode", "MIRROR")
        
        # Route to appropriate distribution method
        if distribution_mode == "SEQUENTIAL":
            return await self._claim_sequential_redis(scene_id, display_id)
        elif distribution_mode == "RANDOM_UNIQUE":
            return await self._claim_random_unique_redis(scene_id, display_id)
        else:  # MIRROR mode
            return await self._claim_mirror_redis(scene_id, display_id)
    
    async def _claim_sequential_redis(self, scene_id: str, display_id: str) -> Dict[str, Any]:
        """Claim from sequential queue using Redis"""
        
        queue_key = f"scene:{scene_id}:sequential_queue"
        client = await self.redis_manager.get_async_client()
        
        # Atomic pop from queue
        content_id = await client.lpop(queue_key)
        
        if not content_id:
            # Check if we need to refill the queue
            await self._refill_sequential_queue(scene_id)
            content_id = await client.lpop(queue_key)
            
            if not content_id:
                return {
                    "status": DistributionStatus.QUEUE_EMPTY,
                    "method": "redis_sequential"
                }
        
        # Create lease
        assignment_id = f"assign_{scene_id}_{display_id}_{int(time.time())}"
        lease_data = {
            "content_id": content_id,
            "display_id": display_id,
            "assigned_at": time.time(),
            "mode": "SEQUENTIAL",
            "assignment_id": assignment_id
        }
        
        lease_key = f"lease:{scene_id}:{display_id}"
        lease_ttl = 30  # 30 second TTL for sequential content
        
        success = await self.redis_manager.set_with_ttl(lease_key, lease_data, lease_ttl)
        
        if not success:
            # Put content back in queue if lease creation failed
            await client.lpush(queue_key, content_id)
            return {
                "status": DistributionStatus.ERROR,
                "error": "Failed to create lease",
                "method": "redis_sequential"
            }
        
        # Broadcast queue status update
        await self._broadcast_queue_update(scene_id, "SEQUENTIAL", display_id, content_id)
        
        return {
            "status": DistributionStatus.ASSIGNED,
            "content_id": content_id,
            "lease_expires_in": lease_ttl,
            "assignment_id": assignment_id,
            "method": "redis_sequential"
        }
    
    async def _claim_random_unique_redis(self, scene_id: str, display_id: str) -> Dict[str, Any]:
        """Claim from shuffle bag using Redis"""
        
        bag_key = f"scene:{scene_id}:shuffle_bag"
        client = await self.redis_manager.get_async_client()
        
        # Atomic pop from shuffle bag
        content_id = await client.lpop(bag_key)
        
        if not content_id:
            # Check if we need to refill the shuffle bag
            await self._refill_shuffle_bag(scene_id)
            content_id = await client.lpop(bag_key)
            
            if not content_id:
                return {
                    "status": DistributionStatus.QUEUE_EMPTY,
                    "method": "redis_random"
                }
        
        # Create lease
        assignment_id = f"assign_{scene_id}_{display_id}_{int(time.time())}"
        lease_data = {
            "content_id": content_id,
            "display_id": display_id,
            "assigned_at": time.time(),
            "mode": "RANDOM_UNIQUE",
            "assignment_id": assignment_id
        }
        
        lease_key = f"lease:{scene_id}:{display_id}"
        lease_ttl = 45  # 45 second TTL for random content (might take longer to process)
        
        success = await self.redis_manager.set_with_ttl(lease_key, lease_data, lease_ttl)
        
        if not success:
            # Put content back in bag if lease creation failed
            await client.lpush(bag_key, content_id)
            return {
                "status": DistributionStatus.ERROR,
                "error": "Failed to create lease",
                "method": "redis_random"
            }
        
        # Broadcast bag status update
        await self._broadcast_queue_update(scene_id, "RANDOM_UNIQUE", display_id, content_id)
        
        return {
            "status": DistributionStatus.ASSIGNED,
            "content_id": content_id,
            "lease_expires_in": lease_ttl,
            "assignment_id": assignment_id,
            "method": "redis_random"
        }
    
    async def _claim_mirror_redis(self, scene_id: str, display_id: str) -> Dict[str, Any]:
        """Get current content for mirror mode"""
        
        # In mirror mode, all displays show the same content
        current_content_key = f"scene:{scene_id}:current_content"
        current_content = await self.redis_manager.get_json(current_content_key)
        
        if not current_content:
            # Initialize mirror mode content
            await self._initialize_mirror_content(scene_id)
            current_content = await self.redis_manager.get_json(current_content_key)
            
            if not current_content:
                return {
                    "status": DistributionStatus.QUEUE_EMPTY,
                    "method": "redis_mirror"
                }
        
        assignment_id = f"mirror_{scene_id}_{display_id}_{int(time.time())}"
        
        return {
            "status": DistributionStatus.ASSIGNED,
            "content_id": current_content["content_id"],
            "assignment_id": assignment_id,
            "method": "redis_mirror",
            "updated_at": current_content.get("updated_at")
        }
    
    async def _claim_via_sql(self, scene_id: str, display_id: str) -> Dict[str, Any]:
        """SQL fallback for content claims when Redis is unavailable"""
        
        if not self.db_session_factory:
            return {
                "status": DistributionStatus.ERROR,
                "error": "No database session factory available",
                "method": "sql_fallback"
            }
        
        # This will be implemented in the next phase
        # For now, return a basic response
        return {
            "status": DistributionStatus.ERROR,
            "error": "SQL fallback not yet implemented",
            "method": "sql_fallback"
        }
    
    async def acknowledge_assignment(self, scene_id: str, display_id: str, 
                                   assignment_id: str, status: str) -> Dict[str, Any]:
        """
        Acknowledge content assignment completion
        
        Args:
            scene_id: Scene identifier
            display_id: Display client identifier
            assignment_id: Assignment identifier from claim response
            status: Completion status (e.g., "displayed", "error")
            
        Returns:
            Dict with acknowledgment status and metadata
        """
        try:
            if await self.is_redis_healthy():
                return await self._acknowledge_via_redis(scene_id, display_id, assignment_id, status)
            else:
                return await self._acknowledge_via_sql(scene_id, display_id, assignment_id, status)
                
        except Exception as e:
            logger.error(f"Error acknowledging assignment {assignment_id}: {e}")
            return {
                "status": DistributionStatus.ERROR,
                "error": str(e)
            }
    
    async def _acknowledge_via_redis(self, scene_id: str, display_id: str, 
                                   assignment_id: str, status: str) -> Dict[str, Any]:
        """Acknowledge assignment using Redis"""
        
        lease_key = f"lease:{scene_id}:{display_id}"
        lease_data = await self.redis_manager.get_json(lease_key)
        
        if not lease_data:
            return {
                "status": DistributionStatus.LEASE_NOT_FOUND,
                "message": "Lease not found or already expired"
            }
        
        # Verify assignment ID matches
        if lease_data.get("assignment_id") != assignment_id:
            return {
                "status": DistributionStatus.ERROR,
                "error": "Assignment ID mismatch"
            }
        
        # Remove lease
        client = await self.redis_manager.get_async_client()
        await client.delete(lease_key)
        
        # Create completion record for analytics
        completion_record = {
            "assignment_id": assignment_id,
            "scene_id": scene_id,
            "display_id": display_id,
            "content_id": lease_data["content_id"],
            "status": status,
            "completed_at": time.time(),
            "lease_duration": time.time() - lease_data["assigned_at"]
        }
        
        # Store completion record with TTL for analytics
        completion_key = f"completion:{assignment_id}"
        await self.redis_manager.set_with_ttl(completion_key, completion_record, 3600)  # 1 hour TTL
        
        # Broadcast completion event
        await self._broadcast_assignment_completion(completion_record)
        
        return {
            "status": DistributionStatus.ACKNOWLEDGED,
            "assignment_id": assignment_id,
            "lease_duration_seconds": completion_record["lease_duration"]
        }
    
    async def _acknowledge_via_sql(self, scene_id: str, display_id: str, 
                                 assignment_id: str, status: str) -> Dict[str, Any]:
        """SQL fallback for acknowledgments"""
        # To be implemented in next phase
        return {
            "status": DistributionStatus.ERROR,
            "error": "SQL fallback acknowledgment not yet implemented"
        }
    
    # Helper methods
    
    async def _get_scene_metadata(self, scene_id: str) -> Dict[str, Any]:
        """Get scene metadata from Redis or initialize defaults"""
        
        meta_key = f"scene:{scene_id}:meta"
        metadata = await self.redis_manager.get_json(meta_key)
        
        if not metadata:
            # Initialize default metadata
            metadata = {
                "mode": "MIRROR",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            await self.redis_manager.set_with_ttl(meta_key, metadata, 86400)  # 24 hour TTL
        
        return metadata
    
    async def _refill_sequential_queue(self, scene_id: str):
        """Refill sequential queue from content set"""
        if not self.content_manager:
            logger.warning(f"Content manager not available for queue refill: {scene_id}")
            return
        
        try:
            # Get content set
            content_set = await self.content_manager.get_content_set(scene_id)
            if not content_set:
                logger.warning(f"No content set found for scene {scene_id}")
                return
            
            content_ids = content_set.get_content_ids()
            if not content_ids:
                logger.warning(f"No content items in set for scene {scene_id}")
                return
            
            # Refill queue
            queue_key = f"scene:{scene_id}:sequential_queue"
            client = await self.redis_manager.get_async_client()
            
            async with self.redis_manager.pipeline() as pipe:
                pipe.delete(queue_key)
                pipe.lpush(queue_key, *content_ids)
                pipe.expire(queue_key, 86400)  # 24 hour TTL
                await pipe.execute()
            
            logger.info(f"Refilled sequential queue for scene {scene_id}: {len(content_ids)} items")
            
        except Exception as e:
            logger.error(f"Error refilling sequential queue for scene {scene_id}: {e}")
    
    async def _refill_shuffle_bag(self, scene_id: str):
        """Refill shuffle bag from content set"""
        if not self.content_manager:
            logger.warning(f"Content manager not available for bag refill: {scene_id}")
            return
        
        try:
            # Get content set
            content_set = await self.content_manager.get_content_set(scene_id)
            if not content_set:
                logger.warning(f"No content set found for scene {scene_id}")
                return
            
            content_ids = content_set.get_content_ids()
            if not content_ids:
                logger.warning(f"No content items in set for scene {scene_id}")
                return
            
            # Shuffle content
            import random
            shuffled_content = content_ids.copy()
            random.shuffle(shuffled_content)
            
            # Refill bag
            bag_key = f"scene:{scene_id}:shuffle_bag"
            client = await self.redis_manager.get_async_client()
            
            async with self.redis_manager.pipeline() as pipe:
                pipe.delete(bag_key)
                pipe.lpush(bag_key, *shuffled_content)
                pipe.expire(bag_key, 86400)  # 24 hour TTL
                await pipe.execute()
            
            logger.info(f"Refilled shuffle bag for scene {scene_id}: {len(content_ids)} items")
            
            # Broadcast new epoch started
            if self.ws_manager:
                await self.ws_manager.broadcast_to_dashboard_clients({
                    "event": "epoch_started",
                    "data": {
                        "scene_id": scene_id,
                        "mode": "RANDOM_UNIQUE",
                        "content_count": len(content_ids),
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
        except Exception as e:
            logger.error(f"Error refilling shuffle bag for scene {scene_id}: {e}")
    
    async def _initialize_mirror_content(self, scene_id: str):
        """Initialize mirror mode content"""
        if not self.content_manager:
            logger.warning(f"Content manager not available for mirror init: {scene_id}")
            return
        
        try:
            # Get content set
            content_set = await self.content_manager.get_content_set(scene_id)
            if not content_set:
                logger.warning(f"No content set found for scene {scene_id}")
                return
            
            content_ids = content_set.get_content_ids()
            if not content_ids:
                logger.warning(f"No content items in set for scene {scene_id}")
                return
            
            # Set current content (first item by default)
            current_content = {
                "content_id": content_ids[0],
                "epoch_id": content_set._epoch_id or f"mirror_{int(time.time())}",
                "updated_at": datetime.now().isoformat(),
                "total_items": len(content_ids)
            }
            
            current_content_key = f"scene:{scene_id}:current_content"
            await self.redis_manager.set_with_ttl(current_content_key, current_content, 86400)
            
            logger.info(f"Initialized mirror content for scene {scene_id}: {current_content['content_id']}")
            
        except Exception as e:
            logger.error(f"Error initializing mirror content for scene {scene_id}: {e}")
    
    async def _broadcast_queue_update(self, scene_id: str, mode: str, display_id: str, content_id: str):
        """Broadcast queue status update via WebSocket"""
        if not self.ws_manager:
            return
        
        try:
            # Get remaining items in queue/bag
            if mode == "SEQUENTIAL":
                queue_key = f"scene:{scene_id}:sequential_queue"
            elif mode == "RANDOM_UNIQUE":
                queue_key = f"scene:{scene_id}:shuffle_bag"
            else:
                return
            
            client = await self.redis_manager.get_async_client()
            remaining = await client.llen(queue_key)
            
            event_data = {
                "event": "queue_updated",
                "data": {
                    "scene_id": scene_id,
                    "mode": mode,
                    "remaining_items": remaining,
                    "assigned_to": display_id,
                    "content_id": content_id,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Broadcast to dashboard clients
            await self.ws_manager.broadcast_to_dashboard_clients(event_data)
            
        except Exception as e:
            logger.error(f"Error broadcasting queue update: {e}")
    
    async def _broadcast_assignment_completion(self, completion_record: Dict[str, Any]):
        """Broadcast assignment completion via WebSocket"""
        if not self.ws_manager:
            return
        
        try:
            event_data = {
                "event": "assignment_completed",
                "data": completion_record
            }
            
            # Broadcast to dashboard clients
            await self.ws_manager.broadcast_to_dashboard_clients(event_data)
            
        except Exception as e:
            logger.error(f"Error broadcasting assignment completion: {e}")
    
    async def get_distribution_status(self, scene_id: str) -> Dict[str, Any]:
        """Get current distribution status for a scene"""
        
        if not await self.is_redis_healthy():
            return {
                "scene_id": scene_id,
                "redis_available": False,
                "error": "Redis not available"
            }
        
        try:
            client = await self.redis_manager.get_async_client()
            
            # Get scene metadata
            scene_meta = await self._get_scene_metadata(scene_id)
            mode = scene_meta.get("mode", "MIRROR")
            
            # Count active leases
            lease_pattern = f"lease:{scene_id}:*"
            lease_keys = await client.keys(lease_pattern)
            
            status = {
                "scene_id": scene_id,
                "distribution_mode": mode,
                "active_leases": len(lease_keys),
                "redis_available": True,
                "queue_status": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Get queue/bag status
            if mode == "SEQUENTIAL":
                queue_key = f"scene:{scene_id}:sequential_queue"
                remaining = await client.llen(queue_key)
                status["queue_status"] = {
                    "type": "sequential_queue",
                    "remaining": remaining
                }
            elif mode == "RANDOM_UNIQUE":
                bag_key = f"scene:{scene_id}:shuffle_bag"
                remaining = await client.llen(bag_key)
                status["queue_status"] = {
                    "type": "shuffle_bag", 
                    "remaining": remaining
                }
            elif mode == "MIRROR":
                current_key = f"scene:{scene_id}:current_content"
                current_content = await self.redis_manager.get_json(current_key)
                status["queue_status"] = {
                    "type": "mirror",
                    "current_content": current_content
                }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting distribution status for scene {scene_id}: {e}")
            return {
                "scene_id": scene_id,
                "redis_available": True,
                "error": str(e)
            }


# Global distribution service instance
distribution_service = None

def get_distribution_service(websocket_manager=None, db_session_factory=None) -> DistributionService:
    """Get global distribution service instance"""
    global distribution_service
    if distribution_service is None:
        distribution_service = DistributionService(websocket_manager, db_session_factory)
    return distribution_service
