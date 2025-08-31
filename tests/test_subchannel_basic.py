"""
Simple test runner for Sub-Channel functionality
Tests BaseChannel interface and SubChannelManager without external dependencies
"""

import json
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Any, List, Tuple
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the classes we're testing
try:
    from base_channel import BaseChannel
    from subchannel_manager import SubChannelManager
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure base_channel.py and subchannel_manager.py are in the same directory")
    sys.exit(1)


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


class TestRunner:
    """Simple test runner"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def run_test(self, test_name: str, test_func):
        """Run a single test"""
        try:
            print(f"Running {test_name}...", end=" ")
            test_func()
            print("PASS")
            self.passed += 1
        except Exception as e:
            print("FAIL")
            self.failed += 1
            error_msg = f"{test_name}: {str(e)}"
            self.errors.append(error_msg)
            print(f"  Error: {str(e)}")
    
    def assert_equal(self, actual, expected, message=""):
        """Simple assertion"""
        if actual != expected:
            msg = f"Expected {expected}, got {actual}"
            if message:
                msg = f"{message}: {msg}"
            raise AssertionError(msg)
    
    def assert_true(self, condition, message=""):
        """Assert condition is true"""
        if not condition:
            msg = "Condition was False"
            if message:
                msg = f"{message}: {msg}"
            raise AssertionError(msg)
    
    def assert_raises(self, exception_type, func, *args, **kwargs):
        """Assert function raises specific exception"""
        try:
            func(*args, **kwargs)
            raise AssertionError(f"Expected {exception_type.__name__} to be raised")
        except exception_type:
            pass  # Expected
        except Exception as e:
            raise AssertionError(f"Expected {exception_type.__name__}, got {type(e).__name__}: {e}")
    
    def summary(self):
        """Print test summary"""
        print(f"\n{'='*50}")
        print(f"Test Results: {self.passed} passed, {self.failed} failed")
        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*50}")
        return self.failed == 0


def test_base_channel_without_subchannels():
    """Test channel that doesn't support sub-channels"""
    with tempfile.TemporaryDirectory() as temp_dir:
        channel = MockChannel(temp_dir, supports_subs=False)
        
        runner.assert_equal(channel.supports_subchannels(), False)
        runner.assert_equal(channel.get_subchannel_config()["enabled"], False)
        runner.assert_equal(channel.get_subchannels(), [])
        
        # Should raise NotImplementedError for sub-channel operations
        runner.assert_raises(NotImplementedError, channel.create_subchannel, {"name": "test"})


def test_base_channel_with_subchannels():
    """Test channel that supports sub-channels"""
    with tempfile.TemporaryDirectory() as temp_dir:
        channel = MockChannel(temp_dir, supports_subs=True)
        
        runner.assert_equal(channel.supports_subchannels(), True)
        runner.assert_equal(channel.get_subchannel_config()["enabled"], True)
        
        # Create sub-channel
        subchannel = channel.create_subchannel({
            "name": "Test Gallery",
            "description": "A test gallery"
        })
        
        runner.assert_equal(subchannel["name"], "Test Gallery")
        runner.assert_true("id" in subchannel)
        
        # List sub-channels
        subchannels = channel.get_subchannels()
        runner.assert_equal(len(subchannels), 1)
        runner.assert_equal(subchannels[0]["name"], "Test Gallery")


def test_subchannel_content_management():
    """Test content assignment to sub-channels"""
    with tempfile.TemporaryDirectory() as temp_dir:
        channel = MockChannel(temp_dir, supports_subs=True)
        
        # Create sub-channel
        subchannel = channel.create_subchannel({"name": "Gallery"})
        subchannel_id = subchannel["id"]
        
        # Add content
        channel.assign_content_to_subchannel(subchannel_id, ["img1", "img2"], "add")
        
        # Get content
        content = channel.get_subchannel_content(subchannel_id)
        runner.assert_equal(content["totalCount"], 2)
        runner.assert_equal(len(content["content"]), 2)
        
        # Remove content
        channel.assign_content_to_subchannel(subchannel_id, ["img1"], "remove")
        content = channel.get_subchannel_content(subchannel_id)
        runner.assert_equal(content["totalCount"], 1)


def test_subchannel_id_generation():
    """Test unique ID generation for sub-channels"""
    with tempfile.TemporaryDirectory() as temp_dir:
        channel = MockChannel(temp_dir, supports_subs=True)
        
        # Create channels with same name
        sub1 = channel.create_subchannel({"name": "Gallery"})
        sub2 = channel.create_subchannel({"name": "Gallery"})
        
        runner.assert_true(sub1["id"] != sub2["id"])
        runner.assert_equal(sub1["id"], "gallery")
        runner.assert_equal(sub2["id"], "gallery_1")


async def test_subchannel_manager():
    """Test SubChannelManager basic functionality"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock channels
        channel_with_subs = MockChannel(f"{temp_dir}/with_subs", supports_subs=True)
        channel_without_subs = MockChannel(f"{temp_dir}/without_subs", supports_subs=False)
        
        channel_registry = {
            "with_subs": channel_with_subs,
            "without_subs": channel_without_subs
        }
        
        manager = SubChannelManager(channel_registry)
        
        # Test configuration
        config = await manager.get_subchannel_config("with_subs")
        runner.assert_equal(config["enabled"], True)
        
        config = await manager.get_subchannel_config("without_subs")
        runner.assert_equal(config["enabled"], False)
        
        # Test listing (initially empty)
        result = await manager.list_subchannels("with_subs")
        runner.assert_equal(result["subChannels"], [])
        
        # Test creation
        subchannel = await manager.create_subchannel("with_subs", {
            "name": "Photo Gallery",
            "description": "Family photos"
        })
        
        runner.assert_equal(subchannel["name"], "Photo Gallery")
        runner.assert_true("id" in subchannel)
        
        # Test listing after creation
        result = await manager.list_subchannels("with_subs")
        runner.assert_equal(len(result["subChannels"]), 1)


def run_async_test(test_func):
    """Simple async test runner"""
    import asyncio
    asyncio.run(test_func())


# Initialize global test runner
runner = TestRunner()

if __name__ == "__main__":
    print("Running Sub-Channel Infrastructure Tests")
    print("="*50)
    
    # Run tests
    runner.run_test("BaseChannel without sub-channels", test_base_channel_without_subchannels)
    runner.run_test("BaseChannel with sub-channels", test_base_channel_with_subchannels)
    runner.run_test("Sub-channel content management", test_subchannel_content_management)
    runner.run_test("Sub-channel ID generation", test_subchannel_id_generation)
    runner.run_test("SubChannelManager", lambda: run_async_test(test_subchannel_manager))
    
    # Print summary
    success = runner.summary()
    
    if success:
        print("\n✅ All tests passed! Phase 1 infrastructure is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
    
    sys.exit(0 if success else 1)
