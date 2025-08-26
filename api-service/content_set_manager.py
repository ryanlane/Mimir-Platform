"""
Content Set Manager for Mimir Platform

This module manages content sets for Redis-based distribution, handling content
discovery from channels, hash calculation for change detection, and epoch management
for coordinated updates across displays.
"""

import json
import hashlib
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

# Import Redis manager and distribution components
try:
    from redis_manager import RedisManager, get_redis_manager
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

class ContentItem:
    """Represents a single content item with metadata"""
    
    def __init__(self, content_id: str, channel_id: str, **metadata):
        self.content_id = content_id
        self.channel_id = channel_id
        self.metadata = metadata
        self.discovered_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "content_id": self.content_id,
            "channel_id": self.channel_id,
            "metadata": self.metadata,
            "discovered_at": self.discovered_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentItem':
        """Create from dictionary"""
        item = cls(data["content_id"], data["channel_id"], **data.get("metadata", {}))
        if "discovered_at" in data:
            item.discovered_at = datetime.fromisoformat(data["discovered_at"])
        return item

class ContentSet:
    """Represents a collection of content items for a scene"""
    
    def __init__(self, scene_id: str, items: List[ContentItem] = None):
        self.scene_id = scene_id
        self.items = items or []
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self._content_hash = None
        self._epoch_id = None
    
    def add_item(self, item: ContentItem):
        """Add content item to set"""
        self.items.append(item)
        self.last_updated = datetime.now()
        self._content_hash = None  # Invalidate hash cache
    
    def remove_item(self, content_id: str) -> bool:
        """Remove content item by ID"""
        initial_count = len(self.items)
        self.items = [item for item in self.items if item.content_id != content_id]
        if len(self.items) != initial_count:
            self.last_updated = datetime.now()
            self._content_hash = None  # Invalidate hash cache
            return True
        return False
    
    def get_content_ids(self) -> List[str]:
        """Get list of content IDs"""
        return [item.content_id for item in self.items]
    
    def get_content_hash(self) -> str:
        """Calculate hash of content set for change detection"""
        if self._content_hash is None:
            # Create deterministic hash based on content IDs and metadata
            content_data = []
            for item in sorted(self.items, key=lambda x: x.content_id):
                item_data = {
                    "id": item.content_id,
                    "channel": item.channel_id,
                    "meta": item.metadata
                }
                content_data.append(item_data)
            
            content_str = json.dumps(content_data, sort_keys=True)
            self._content_hash = hashlib.sha256(content_str.encode()).hexdigest()
        
        return self._content_hash
    
    def generate_epoch_id(self) -> str:
        """Generate new epoch ID for this content set"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hash_suffix = self.get_content_hash()[:8]
        self._epoch_id = f"ep_{timestamp}_{hash_suffix}"
        return self._epoch_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "scene_id": self.scene_id,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "content_hash": self.get_content_hash(),
            "epoch_id": self._epoch_id
        }

class ContentSetManager:
    """
    Manages content sets for Redis distribution system
    
    Handles content discovery from channels, change detection, and Redis queue population.
    """
    
    def __init__(self, channel_discovery=None):
        """
        Initialize content set manager
        
        Args:
            channel_discovery: Channel discovery instance for content lookup
        """
        self.channel_discovery = channel_discovery
        self.redis_manager = None
        self.content_sets: Dict[str, ContentSet] = {}  # scene_id -> ContentSet
        
        # Initialize Redis if available
        if REDIS_AVAILABLE:
            try:
                self.redis_manager = get_redis_manager()
            except Exception as e:
                logger.warning(f"Redis initialization failed in ContentSetManager: {e}")
    
    async def discover_content_for_scene(self, scene_id: str, channels: List[str]) -> ContentSet:
        """
        Discover content items from channels for a scene
        
        Args:
            scene_id: Scene identifier
            channels: List of channel IDs to discover content from
            
        Returns:
            ContentSet with discovered content items
        """
        content_set = ContentSet(scene_id)
        
        logger.info(f"Discovering content for scene {scene_id} from {len(channels)} channels")
        
        for channel_id in channels:
            try:
                # Get content from channel
                channel_content = await self._get_channel_content(channel_id)
                
                for content_data in channel_content:
                    content_item = ContentItem(
                        content_id=content_data.get("id", f"{channel_id}_{len(content_set.items)}"),
                        channel_id=channel_id,
                        **content_data
                    )
                    content_set.add_item(content_item)
                
                logger.debug(f"Found {len(channel_content)} items from channel {channel_id}")
                
            except Exception as e:
                logger.error(f"Error discovering content from channel {channel_id}: {e}")
        
        logger.info(f"Discovered {len(content_set.items)} total content items for scene {scene_id}")
        return content_set
    
    async def _get_channel_content(self, channel_id: str) -> List[Dict[str, Any]]:
        """
        Get content items from a specific channel
        
        Args:
            channel_id: Channel identifier
            
        Returns:
            List of content item dictionaries
        """
        if not self.channel_discovery:
            # Mock content for testing
            return self._generate_mock_content(channel_id)
        
        try:
            # Get channel instance
            channel = self.channel_discovery.loaded_channels.get(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found in loaded channels")
                return []
            
            # Different strategies based on channel type
            if hasattr(channel, 'get_content_list'):
                # Channel has explicit content list method
                return await channel.get_content_list()
            elif hasattr(channel, 'get_images'):
                # Photo frame or gallery type channel
                images = await channel.get_images()
                return [{"id": f"img_{i}", "type": "image", "path": img} for i, img in enumerate(images)]
            elif hasattr(channel, 'current_image_path'):
                # Single image channel
                return [{"id": "current", "type": "image", "path": channel.current_image_path}]
            else:
                logger.warning(f"Channel {channel_id} does not expose content discovery interface")
                return self._generate_mock_content(channel_id)
                
        except Exception as e:
            logger.error(f"Error getting content from channel {channel_id}: {e}")
            return []
    
    def _generate_mock_content(self, channel_id: str) -> List[Dict[str, Any]]:
        """Generate mock content for testing purposes"""
        mock_content = []
        
        # Generate 5-15 mock content items
        count = random.randint(5, 15)
        for i in range(count):
            content_type = random.choice(["image", "video", "text"])
            mock_content.append({
                "id": f"{channel_id}_content_{i:03d}",
                "type": content_type,
                "path": f"/mock/{channel_id}/{content_type}_{i:03d}.jpg",
                "size": random.randint(100000, 5000000),
                "resolution": [random.choice([800, 1024, 1280, 1920]), random.choice([600, 768, 720, 1080])],
                "created_at": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat()
            })
        
        return mock_content
    
    async def update_content_set(self, scene_id: str, channels: List[str], force_update: bool = False) -> Dict[str, Any]:
        """
        Update content set for a scene and manage Redis queues
        
        Args:
            scene_id: Scene identifier
            channels: List of channel IDs
            force_update: Force update even if content hasn't changed
            
        Returns:
            Dict with update status and metadata
        """
        try:
            # Discover current content
            new_content_set = await self.discover_content_for_scene(scene_id, channels)
            
            # Get existing content set hash from Redis
            existing_hash = None
            if self.redis_manager and await self.redis_manager.is_healthy():
                content_set_key = f"scene:{scene_id}:content_set"
                existing_data = await self.redis_manager.get_json(content_set_key)
                if existing_data:
                    existing_hash = existing_data.get("source_hash")
            
            # Check if content has changed
            new_hash = new_content_set.get_content_hash()
            
            if not force_update and existing_hash == new_hash:
                return {
                    "status": "unchanged",
                    "scene_id": scene_id,
                    "content_hash": new_hash,
                    "item_count": len(new_content_set.items),
                    "message": "Content set unchanged"
                }
            
            # Generate new epoch
            epoch_id = new_content_set.generate_epoch_id()
            
            # Update content set
            result = await self._update_redis_content_set(scene_id, new_content_set, epoch_id)
            
            # Store in local cache
            self.content_sets[scene_id] = new_content_set
            
            logger.info(f"Content set updated for scene {scene_id}: {len(new_content_set.items)} items, epoch {epoch_id}")
            
            return {
                "status": "updated",
                "scene_id": scene_id,
                "epoch_id": epoch_id,
                "content_hash": new_hash,
                "previous_hash": existing_hash,
                "item_count": len(new_content_set.items),
                "redis_available": self.redis_manager is not None,
                **result
            }
            
        except Exception as e:
            logger.error(f"Error updating content set for scene {scene_id}: {e}")
            return {
                "status": "error",
                "scene_id": scene_id,
                "error": str(e)
            }
    
    async def _update_redis_content_set(self, scene_id: str, content_set: ContentSet, epoch_id: str) -> Dict[str, Any]:
        """Update content set in Redis with atomic operations"""
        
        if not self.redis_manager or not await self.redis_manager.is_healthy():
            return {"redis_updated": False, "reason": "Redis not available"}
        
        try:
            # Use pipeline for atomic operations
            async with self.redis_manager.pipeline() as pipe:
                content_set_key = f"scene:{scene_id}:content_set"
                content_items_key = f"scene:{scene_id}:content_items"
                
                # Update content set metadata
                content_set_data = {
                    "source_hash": content_set.get_content_hash(),
                    "epoch_id": epoch_id,
                    "updated_at": datetime.now().isoformat(),
                    "item_count": len(content_set.items),
                    "channels": list(set(item.channel_id for item in content_set.items))
                }
                
                pipe.hset(content_set_key, mapping=content_set_data)
                
                # Clear and repopulate content items
                pipe.delete(content_items_key)
                if content_set.items:
                    content_ids = content_set.get_content_ids()
                    pipe.lpush(content_items_key, *content_ids)
                
                # Set TTL on content set (24 hours)
                pipe.expire(content_set_key, 86400)
                pipe.expire(content_items_key, 86400)
                
                # Execute pipeline
                results = pipe.execute()
                
            # Update distribution queues based on scene mode
            await self._update_distribution_queues(scene_id, content_set, epoch_id)
            
            return {
                "redis_updated": True,
                "pipeline_results": len(results),
                "queues_updated": True
            }
            
        except Exception as e:
            logger.error(f"Error updating Redis content set for scene {scene_id}: {e}")
            return {
                "redis_updated": False,
                "error": str(e)
            }
    
    async def _update_distribution_queues(self, scene_id: str, content_set: ContentSet, epoch_id: str):
        """Update distribution queues/bags based on scene mode"""
        
        if not self.redis_manager:
            return
        
        try:
            # Get scene distribution mode
            meta_key = f"scene:{scene_id}:meta"
            scene_meta = await self.redis_manager.get_json(meta_key) or {}
            mode = scene_meta.get("mode", "MIRROR")
            
            content_ids = content_set.get_content_ids()
            
            if not content_ids:
                logger.warning(f"No content items to populate queues for scene {scene_id}")
                return
            
            async with self.redis_manager.pipeline() as pipe:
                
                if mode == "SEQUENTIAL":
                    # Clear and populate sequential queue
                    queue_key = f"scene:{scene_id}:sequential_queue"
                    pipe.delete(queue_key)
                    pipe.lpush(queue_key, *content_ids)
                    pipe.expire(queue_key, 86400)  # 24 hour TTL
                    
                elif mode == "RANDOM_UNIQUE":
                    # Clear and populate shuffle bag
                    bag_key = f"scene:{scene_id}:shuffle_bag"
                    shuffled_content = content_ids.copy()
                    random.shuffle(shuffled_content)
                    
                    pipe.delete(bag_key)
                    pipe.lpush(bag_key, *shuffled_content)
                    pipe.expire(bag_key, 86400)  # 24 hour TTL
                    
                elif mode == "MIRROR":
                    # Set current content for mirror mode
                    current_content_key = f"scene:{scene_id}:current_content"
                    current_content = {
                        "content_id": content_ids[0] if content_ids else None,
                        "epoch_id": epoch_id,
                        "updated_at": datetime.now().isoformat(),
                        "total_items": len(content_ids)
                    }
                    
                    await self.redis_manager.set_with_ttl(current_content_key, current_content, 86400)
                
                # Update scene metadata with new epoch
                scene_meta.update({
                    "content_epoch": epoch_id,
                    "content_updated_at": datetime.now().isoformat(),
                    "content_item_count": len(content_ids)
                })
                
                await self.redis_manager.set_with_ttl(meta_key, scene_meta, 86400)
                
                # Execute queue updates
                if mode in ["SEQUENTIAL", "RANDOM_UNIQUE"]:
                    results = pipe.execute()
                    logger.info(f"Updated {mode} queue for scene {scene_id}: {len(content_ids)} items")
                
        except Exception as e:
            logger.error(f"Error updating distribution queues for scene {scene_id}: {e}")
    
    async def get_content_set(self, scene_id: str) -> Optional[ContentSet]:
        """Get content set for a scene (from cache or Redis)"""
        
        # Check local cache first
        if scene_id in self.content_sets:
            return self.content_sets[scene_id]
        
        # Try to load from Redis
        if self.redis_manager and await self.redis_manager.is_healthy():
            try:
                content_items_key = f"scene:{scene_id}:content_items"
                content_ids = []
                
                client = await self.redis_manager.get_async_client()
                content_ids = await client.lrange(content_items_key, 0, -1)
                
                if content_ids:
                    # Create content set from Redis data
                    content_set = ContentSet(scene_id)
                    for content_id in content_ids:
                        # Create basic content items (full metadata would require additional storage)
                        item = ContentItem(content_id, "unknown")
                        content_set.add_item(item)
                    
                    self.content_sets[scene_id] = content_set
                    return content_set
                
            except Exception as e:
                logger.error(f"Error loading content set from Redis for scene {scene_id}: {e}")
        
        return None
    
    async def reset_distribution_queues(self, scene_id: str) -> Dict[str, Any]:
        """Reset all distribution queues for a scene"""
        
        if not self.redis_manager or not await self.redis_manager.is_healthy():
            return {"status": "error", "message": "Redis not available"}
        
        try:
            # Get content set
            content_set = await self.get_content_set(scene_id)
            if not content_set:
                return {"status": "error", "message": "Content set not found"}
            
            # Generate new epoch
            epoch_id = content_set.generate_epoch_id()
            
            # Update queues
            await self._update_distribution_queues(scene_id, content_set, epoch_id)
            
            return {
                "status": "reset",
                "scene_id": scene_id,
                "epoch_id": epoch_id,
                "content_items": len(content_set.items)
            }
            
        except Exception as e:
            logger.error(f"Error resetting distribution queues for scene {scene_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_content_set_info(self, scene_id: str) -> Dict[str, Any]:
        """Get detailed information about a content set"""
        
        info = {
            "scene_id": scene_id,
            "local_cache": scene_id in self.content_sets,
            "redis_available": self.redis_manager is not None and await self.redis_manager.is_healthy()
        }
        
        # Get from local cache
        if scene_id in self.content_sets:
            content_set = self.content_sets[scene_id]
            info.update({
                "item_count": len(content_set.items),
                "content_hash": content_set.get_content_hash(),
                "created_at": content_set.created_at.isoformat(),
                "last_updated": content_set.last_updated.isoformat(),
                "epoch_id": content_set._epoch_id,
                "channels": list(set(item.channel_id for item in content_set.items))
            })
        
        # Get from Redis
        if info["redis_available"]:
            try:
                content_set_key = f"scene:{scene_id}:content_set"
                redis_data = await self.redis_manager.get_json(content_set_key)
                if redis_data:
                    info["redis_data"] = redis_data
                
                # Get queue status
                queue_status = {}
                client = await self.redis_manager.get_async_client()
                
                for queue_type, key_pattern in [
                    ("sequential_queue", f"scene:{scene_id}:sequential_queue"),
                    ("shuffle_bag", f"scene:{scene_id}:shuffle_bag"),
                    ("current_content", f"scene:{scene_id}:current_content")
                ]:
                    if queue_type == "current_content":
                        content = await self.redis_manager.get_json(key_pattern)
                        queue_status[queue_type] = content
                    else:
                        length = await client.llen(key_pattern)
                        queue_status[queue_type] = {"length": length}
                
                info["queue_status"] = queue_status
                
            except Exception as e:
                info["redis_error"] = str(e)
        
        return info


# Global content set manager instance
content_set_manager = None

def get_content_set_manager(channel_discovery=None) -> ContentSetManager:
    """Get global content set manager instance"""
    global content_set_manager
    if content_set_manager is None:
        content_set_manager = ContentSetManager(channel_discovery)
    return content_set_manager
