"""
Unit tests for Sub-Channel functionality
Tests BaseChannel interface and SubChannelManager
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Tuple

# Import the classes we're testing
import sys
sys.path.append('.')
from base_channel import BaseChannel
from subchannel_manager import SubChannelManager


class MockChannel(BaseChannel):
    """Mock channel implementation for testing"""
    
    def __init__(self, channel_dir: str, supports_subs: bool = False):
        # Create mock config
        self.channel_dir = Path(channel_dir)
        self._config = {
            "id": "test_channel",
            "name": "Test Channel",
            "version": "1.0.0"
        }
        self._supports_subs = supports_subs
        self._subchannels = []
        
        # State tracking
        self.last_update = None
        self.last_error = None
        self.current_image_id = None
    
    def supports_subchannels(self) -> bool:
        return self._supports_subs
    
    def get_subchannel_config(self) -> Dict[str, Any]:
        if not self._supports_subs:
            return super().get_subchannel_config()
        
        return {
            "enabled": True,
            "label": "Test Sub-channel",
            "labelPlural": "Test Sub-channels",
            "supports_tagging": True,
            "supports_multiple_membership": True,
            "allowCustom": True
        }
    
    def get_subchannels(self) -> List[Dict[str, Any]]:
        return self._subchannels
    
    def create_subchannel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._supports_subs:
            raise NotImplementedError("Channel does not support sub-channels")
        
        subchannel_id = self._generate_subchannel_id(data['name'])
        subchannel = {
            "id": subchannel_id,
            "name": data['name'],
            "description": data.get('description', ''),
            "contentIds": [],
            "tags": data.get('tags', []),
            "created": "2024-08-23T10:00:00Z"
        }
        
        self._subchannels.append(subchannel)
        return subchannel
    
    def update_subchannel(self, subchannel_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._supports_subs:
            raise NotImplementedError("Channel does not support sub-channels")
        
        for i, subchannel in enumerate(self._subchannels):
            if subchannel['id'] == subchannel_id:
                subchannel.update(data)
                return subchannel
        
        raise ValueError(f"Sub-channel '{subchannel_id}' not found")
    
    def delete_subchannel(self, subchannel_id: str) -> bool:
        if not self._supports_subs:
            raise NotImplementedError("Channel does not support sub-channels")
        
        for i, subchannel in enumerate(self._subchannels):
            if subchannel['id'] == subchannel_id:
                del self._subchannels[i]
                return True
        
        raise ValueError(f"Sub-channel '{subchannel_id}' not found")
    
    def assign_content_to_subchannel(self, subchannel_id: str, content_ids: List[str], action: str = "add") -> bool:
        if not self._supports_subs:
            raise NotImplementedError("Channel does not support sub-channels")
        
        for subchannel in self._subchannels:
            if subchannel['id'] == subchannel_id:
                if action == "set":
                    subchannel['contentIds'] = content_ids
                elif action == "add":
                    subchannel['contentIds'].extend(content_ids)
                elif action == "remove":
                    subchannel['contentIds'] = [c for c in subchannel['contentIds'] if c not in content_ids]
                return True
        
        raise ValueError(f"Sub-channel '{subchannel_id}' not found")
    
    def get_subchannel_content(self, subchannel_id: str, limit=None, offset=None) -> Dict[str, Any]:
        if not self._supports_subs:
            raise NotImplementedError("Channel does not support sub-channels")
        
        for subchannel in self._subchannels:
            if subchannel['id'] == subchannel_id:
                content_ids = subchannel['contentIds']
                
                # Apply pagination
                if offset:
                    content_ids = content_ids[offset:]
                if limit:
                    content_ids = content_ids[:limit]
                
                return {
                    "content": [{"id": cid, "name": f"Content {cid}"} for cid in content_ids],
                    "totalCount": len(subchannel['contentIds'])
                }
        
        raise ValueError(f"Sub-channel '{subchannel_id}' not found")
    
    # Required abstract methods
    async def render_image(self, resolution: Tuple[int, int], orientation: str = "landscape", 
                          settings: Dict[str, Any] = None, subchannel_id: str = None) -> str:
        return "/test/image.jpg"
    
    async def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, str]:
        return {}
    
    def get_status(self) -> Dict[str, Any]:
        return {"status": "ok"}


class TestBaseChannel:
    """Test BaseChannel interface"""
    
    def test_channel_without_subchannels(self):
        """Test channel that doesn't support sub-channels"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock config file
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({"id": "test", "name": "Test"}))
            
            channel = MockChannel(temp_dir, supports_subs=False)
            
            assert not channel.supports_subchannels()
            assert channel.get_subchannel_config()["enabled"] is False
            assert channel.get_subchannels() == []
            
            # Should raise NotImplementedError for sub-channel operations
            with pytest.raises(NotImplementedError):
                channel.create_subchannel({"name": "test"})
    
    def test_channel_with_subchannels(self):
        """Test channel that supports sub-channels"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({"id": "test", "name": "Test"}))
            
            channel = MockChannel(temp_dir, supports_subs=True)
            
            assert channel.supports_subchannels()
            assert channel.get_subchannel_config()["enabled"] is True
            
            # Create sub-channel
            subchannel = channel.create_subchannel({
                "name": "Test Gallery",
                "description": "A test gallery"
            })
            
            assert subchannel["name"] == "Test Gallery"
            assert "id" in subchannel
            
            # List sub-channels
            subchannels = channel.get_subchannels()
            assert len(subchannels) == 1
            assert subchannels[0]["name"] == "Test Gallery"
    
    def test_subchannel_content_management(self):
        """Test content assignment to sub-channels"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({"id": "test", "name": "Test"}))
            
            channel = MockChannel(temp_dir, supports_subs=True)
            
            # Create sub-channel
            subchannel = channel.create_subchannel({"name": "Gallery"})
            subchannel_id = subchannel["id"]
            
            # Add content
            channel.assign_content_to_subchannel(subchannel_id, ["img1", "img2"], "add")
            
            # Get content
            content = channel.get_subchannel_content(subchannel_id)
            assert content["totalCount"] == 2
            assert len(content["content"]) == 2
            
            # Remove content
            channel.assign_content_to_subchannel(subchannel_id, ["img1"], "remove")
            content = channel.get_subchannel_content(subchannel_id)
            assert content["totalCount"] == 1
    
    def test_subchannel_id_generation(self):
        """Test unique ID generation for sub-channels"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(json.dumps({"id": "test", "name": "Test"}))
            
            channel = MockChannel(temp_dir, supports_subs=True)
            
            # Create channels with same name
            sub1 = channel.create_subchannel({"name": "Gallery"})
            sub2 = channel.create_subchannel({"name": "Gallery"})
            
            assert sub1["id"] != sub2["id"]
            assert sub1["id"] == "gallery"
            assert sub2["id"] == "gallery_1"


class TestSubChannelManager:
    """Test SubChannelManager"""
    
    def setup_method(self):
        """Set up test channels"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock channels
        self.channel_with_subs = MockChannel(f"{self.temp_dir}/with_subs", supports_subs=True)
        self.channel_without_subs = MockChannel(f"{self.temp_dir}/without_subs", supports_subs=False)
        
        self.channel_registry = {
            "with_subs": self.channel_with_subs,
            "without_subs": self.channel_without_subs
        }
        
        self.manager = SubChannelManager(self.channel_registry)
    
    @pytest.mark.asyncio
    async def test_get_subchannel_config(self):
        """Test getting sub-channel configuration"""
        # Channel with sub-channels
        config = await self.manager.get_subchannel_config("with_subs")
        assert config["enabled"] is True
        
        # Channel without sub-channels
        config = await self.manager.get_subchannel_config("without_subs")
        assert config["enabled"] is False
        
        # Non-existent channel
        with pytest.raises(Exception):  # Should be HTTPException in real FastAPI
            await self.manager.get_subchannel_config("nonexistent")
    
    @pytest.mark.asyncio
    async def test_list_subchannels(self):
        """Test listing sub-channels"""
        # Channel without sub-channels
        result = await self.manager.list_subchannels("without_subs")
        assert result["subChannels"] == []
        
        # Channel with sub-channels (initially empty)
        result = await self.manager.list_subchannels("with_subs")
        assert result["subChannels"] == []
        
        # Add a sub-channel and test again
        await self.manager.create_subchannel("with_subs", {"name": "Test Gallery"})
        result = await self.manager.list_subchannels("with_subs")
        assert len(result["subChannels"]) == 1
    
    @pytest.mark.asyncio
    async def test_create_subchannel(self):
        """Test creating sub-channels"""
        # Valid creation
        result = await self.manager.create_subchannel("with_subs", {
            "name": "Photo Gallery",
            "description": "Family photos"
        })
        
        assert result["name"] == "Photo Gallery"
        assert "id" in result
        
        # Channel doesn't support sub-channels
        with pytest.raises(Exception):
            await self.manager.create_subchannel("without_subs", {"name": "Test"})
        
        # Missing name
        with pytest.raises(Exception):
            await self.manager.create_subchannel("with_subs", {"description": "No name"})
    
    @pytest.mark.asyncio
    async def test_subchannel_crud_operations(self):
        """Test complete CRUD operations on sub-channels"""
        # Create
        subchannel = await self.manager.create_subchannel("with_subs", {
            "name": "Original Name"
        })
        subchannel_id = subchannel["id"]
        
        # Read
        details = await self.manager.get_subchannel_details("with_subs", subchannel_id)
        assert details["name"] == "Original Name"
        
        # Update
        updated = await self.manager.update_subchannel("with_subs", subchannel_id, {
            "name": "Updated Name"
        })
        assert updated["name"] == "Updated Name"
        
        # Delete
        result = await self.manager.delete_subchannel("with_subs", subchannel_id)
        assert result["success"] is True
        
        # Verify deletion
        with pytest.raises(Exception):
            await self.manager.get_subchannel_details("with_subs", subchannel_id)
    
    @pytest.mark.asyncio
    async def test_content_assignment(self):
        """Test content assignment to sub-channels"""
        # Create sub-channel
        subchannel = await self.manager.create_subchannel("with_subs", {"name": "Gallery"})
        subchannel_id = subchannel["id"]
        
        # Assign content
        result = await self.manager.assign_content_to_subchannel(
            "with_subs", 
            subchannel_id, 
            {"contentIds": ["img1", "img2"], "action": "add"}
        )
        assert result["success"] is True
        
        # Get content
        content = await self.manager.get_subchannel_content("with_subs", subchannel_id)
        assert content["totalCount"] == 2
        
        # Remove content
        await self.manager.assign_content_to_subchannel(
            "with_subs",
            subchannel_id,
            {"contentIds": ["img1"], "action": "remove"}
        )
        
        content = await self.manager.get_subchannel_content("with_subs", subchannel_id)
        assert content["totalCount"] == 1


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
