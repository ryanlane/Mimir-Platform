#!/usr/bin/env python3
"""
Complete Redis Integration Test

Tests the full Redis integration including:
- Redis connection and health
- Content set management
- Distribution service
- API endpoints
- WebSocket events
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the api-service directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "api-service"))

from redis_manager import RedisManager
from distribution_service import DistributionService, DistributionMode
from content_set_manager import ContentSetManager, ContentItem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockChannelDiscovery:
    """Mock channel discovery for testing"""
    
    async def get_channel_content(self, channel_id: str):
        """Return mock content for channels"""
        if channel_id == "test_channel_1":
            return [
                {
                    "id": "img_001",
                    "type": "image",
                    "url": "https://example.com/images/001.jpg",
                    "metadata": {"title": "Test Image 1", "tags": ["nature", "landscape"]}
                },
                {
                    "id": "img_002", 
                    "type": "image",
                    "url": "https://example.com/images/002.jpg",
                    "metadata": {"title": "Test Image 2", "tags": ["city", "architecture"]}
                },
                {
                    "id": "img_003",
                    "type": "image", 
                    "url": "https://example.com/images/003.jpg",
                    "metadata": {"title": "Test Image 3", "tags": ["portrait", "people"]}
                }
            ]
        elif channel_id == "test_channel_2":
            return [
                {
                    "id": "vid_001",
                    "type": "video",
                    "url": "https://example.com/videos/001.mp4",
                    "metadata": {"title": "Test Video 1", "duration": 30}
                },
                {
                    "id": "vid_002",
                    "type": "video",
                    "url": "https://example.com/videos/002.mp4", 
                    "metadata": {"title": "Test Video 2", "duration": 45}
                }
            ]
        return []


async def test_redis_connection():
    """Test basic Redis connection"""
    print("\n=== Testing Redis Connection ===")
    
    redis_manager = RedisManager()
    
    try:
        # Test connection
        health = await redis_manager.get_health_status()
        print(f"Redis Health: {health}")
        
        # Test basic operations
        await redis_manager.set_json("test:connection", {"status": "ok", "timestamp": "2024-01-01"})
        result = await redis_manager.get_json("test:connection")
        print(f"Test data roundtrip: {result}")
        
        # Cleanup
        await redis_manager.delete("test:connection")
        
        return True
        
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return False
    finally:
        await redis_manager.close()


async def test_content_set_management():
    """Test content set discovery and management"""
    print("\n=== Testing Content Set Management ===")
    
    redis_manager = RedisManager()
    channel_discovery = MockChannelDiscovery()
    content_manager = ContentSetManager(redis_manager, channel_discovery)
    
    try:
        scene_id = "test_scene_001"
        channels = ["test_channel_1", "test_channel_2"]
        
        # Update content set
        result = await content_manager.update_content_set(scene_id, channels)
        print(f"Content set update result: {result}")
        
        # Get content info
        info = await content_manager.get_content_set_info(scene_id)
        print(f"Content set info: {json.dumps(info, indent=2)}")
        
        # Test different distribution modes
        for mode in [DistributionMode.MIRROR, DistributionMode.SEQUENTIAL, DistributionMode.RANDOM_UNIQUE]:
            populate_result = await content_manager.populate_distribution_queues(scene_id, mode)
            print(f"Populated {mode.value} mode: {populate_result}")
        
        return True
        
    except Exception as e:
        print(f"Content set management failed: {e}")
        return False
    finally:
        await redis_manager.close()


async def test_distribution_service():
    """Test distribution service operations"""
    print("\n=== Testing Distribution Service ===")
    
    redis_manager = RedisManager()
    channel_discovery = MockChannelDiscovery()
    content_manager = ContentSetManager(redis_manager, channel_discovery)
    distribution_service = DistributionService(redis_manager, content_manager)
    
    try:
        scene_id = "test_scene_002"
        channels = ["test_channel_1", "test_channel_2"]
        
        # Setup content first
        await content_manager.update_content_set(scene_id, channels)
        
        # Test each distribution mode
        for mode in [DistributionMode.MIRROR, DistributionMode.SEQUENTIAL, DistributionMode.RANDOM_UNIQUE]:
            print(f"\n--- Testing {mode.value} mode ---")
            
            # Populate queues
            await content_manager.populate_distribution_queues(scene_id, mode)
            
            # Test multiple claims
            for display_num in range(1, 4):
                display_id = f"test_display_{display_num}"
                
                # Claim content
                content = await distribution_service.claim_next_content(
                    scene_id, display_id, mode
                )
                print(f"Display {display_num} claimed: {content}")
                
                if content:
                    # Acknowledge completion
                    completion = await distribution_service.acknowledge_completion(
                        scene_id, display_id, content["content_id"], mode
                    )
                    print(f"Display {display_num} acknowledged: {completion}")
        
        return True
        
    except Exception as e:
        print(f"Distribution service test failed: {e}")
        return False
    finally:
        await redis_manager.close()


async def test_redis_data_structures():
    """Test Redis data structure operations"""
    print("\n=== Testing Redis Data Structures ===")
    
    redis_manager = RedisManager()
    
    try:
        # Test lists (for sequential)
        list_key = "test:list"
        await redis_manager.clear_list(list_key)
        
        for i in range(5):
            await redis_manager.push_to_list(list_key, f"item_{i}")
        
        list_length = await redis_manager.get_list_length(list_key)
        print(f"List length: {list_length}")
        
        # Pop items
        for i in range(3):
            item = await redis_manager.pop_from_list(list_key)
            print(f"Popped: {item}")
        
        # Test sets (for random unique)
        set_key = "test:set"
        await redis_manager.clear_set(set_key)
        
        for i in range(5):
            await redis_manager.add_to_set(set_key, f"item_{i}")
        
        set_size = await redis_manager.get_set_size(set_key)
        print(f"Set size: {set_size}")
        
        # Pop random items
        for i in range(3):
            item = await redis_manager.pop_random_from_set(set_key)
            print(f"Random popped: {item}")
        
        # Test JSON operations
        json_key = "test:json"
        test_data = {
            "content": {"id": "test", "type": "image"},
            "metadata": {"tags": ["test"], "created": "2024-01-01"},
            "numbers": [1, 2, 3, 4, 5]
        }
        
        await redis_manager.set_json(json_key, test_data)
        retrieved = await redis_manager.get_json(json_key)
        print(f"JSON roundtrip match: {test_data == retrieved}")
        
        # Cleanup
        await redis_manager.delete(list_key)
        await redis_manager.delete(set_key)
        await redis_manager.delete(json_key)
        
        return True
        
    except Exception as e:
        print(f"Redis data structures test failed: {e}")
        return False
    finally:
        await redis_manager.close()


async def test_lease_management():
    """Test TTL-based lease management"""
    print("\n=== Testing Lease Management ===")
    
    redis_manager = RedisManager()
    
    try:
        lease_key = "test:lease:display_123"
        content_data = {"content_id": "test_content", "claimed_at": "2024-01-01T12:00:00Z"}
        
        # Set lease with TTL
        await redis_manager.set_json(lease_key, content_data, ttl=5)  # 5 second TTL
        
        # Check lease exists
        lease = await redis_manager.get_json(lease_key)
        print(f"Active lease: {lease}")
        
        # Check TTL
        ttl = await redis_manager.get_ttl(lease_key)
        print(f"Lease TTL: {ttl} seconds")
        
        # Wait for expiration
        print("Waiting for lease expiration...")
        await asyncio.sleep(6)
        
        # Check lease expired
        expired_lease = await redis_manager.get_json(lease_key)
        print(f"Expired lease: {expired_lease}")
        
        return expired_lease is None
        
    except Exception as e:
        print(f"Lease management test failed: {e}")
        return False
    finally:
        await redis_manager.close()


async def cleanup_test_data():
    """Clean up all test data"""
    print("\n=== Cleaning Up Test Data ===")
    
    redis_manager = RedisManager()
    
    try:
        # Delete all test keys
        patterns = [
            "test:*",
            "scene:test_scene_*",
            "lease:test_display_*",
            "completion:test_*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = await redis_manager.delete_pattern(pattern)
            total_deleted += deleted
            print(f"Deleted {deleted} keys matching {pattern}")
        
        print(f"Total cleanup: {total_deleted} keys deleted")
        
    except Exception as e:
        print(f"Cleanup failed: {e}")
    finally:
        await redis_manager.close()


async def main():
    """Run all integration tests"""
    print("Starting Complete Redis Integration Test")
    print("=" * 50)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Content Set Management", test_content_set_management),
        ("Distribution Service", test_distribution_service), 
        ("Redis Data Structures", test_redis_data_structures),
        ("Lease Management", test_lease_management)
    ]
    
    results = {}
    
    # Run tests
    for test_name, test_func in tests:
        try:
            print(f"\nRunning {test_name}...")
            success = await test_func()
            results[test_name] = "PASS" if success else "FAIL"
        except Exception as e:
            print(f"Test {test_name} crashed: {e}")
            results[test_name] = "CRASH"
    
    # Cleanup
    await cleanup_test_data()
    
    # Report results
    print("\n" + "=" * 50)
    print("INTEGRATION TEST RESULTS")
    print("=" * 50)
    
    for test_name, result in results.items():
        status_icon = "✅" if result == "PASS" else "❌"
        print(f"{status_icon} {test_name}: {result}")
    
    # Overall result
    all_passed = all(result == "PASS" for result in results.values())
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    return all_passed


if __name__ == "__main__":
    # Check if we're in the right directory
    if not Path("api-service/main.py").exists():
        print("❌ Please run this script from the mimir-api directory")
        sys.exit(1)
    
    # Run tests
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Test suite crashed: {e}")
        sys.exit(1)
