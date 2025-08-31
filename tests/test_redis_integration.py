#!/usr/bin/env python3
"""
Redis Integration Test Script for Mimir Platform

This script tests the Redis connection and basic distribution functionality.
Run this to verify your Redis setup is working correctly.
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add the api-service directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api-service'))

async def test_redis_connection():
    """Test basic Redis connection"""
    print("🔄 Testing Redis connection...")
    
    try:
        from redis_manager import RedisManager
        
        # Create Redis manager
        redis_manager = RedisManager()
        
        # Test health
        is_healthy = await redis_manager.is_healthy()
        if is_healthy:
            print("✅ Redis connection: HEALTHY")
            
            # Get detailed health status
            health_status = await redis_manager.get_health_status()
            print(f"   Redis version: {health_status.get('redis_version', 'unknown')}")
            print(f"   Memory used: {health_status.get('memory', {}).get('used_memory_human', 'unknown')}")
            print(f"   Ping latency: {health_status.get('ping_duration_ms', 'unknown')}ms")
            
            return True
        else:
            print("❌ Redis connection: FAILED")
            return False
            
    except ImportError as e:
        print(f"❌ Redis import failed: {e}")
        print("   Make sure redis and aioredis are installed: pip install redis aioredis")
        return False
    except Exception as e:
        print(f"❌ Redis connection error: {e}")
        print("   Make sure Redis is running on localhost:6379")
        return False

async def test_redis_operations():
    """Test basic Redis operations"""
    print("\n🔄 Testing Redis operations...")
    
    try:
        from redis_manager import RedisManager
        
        redis_manager = RedisManager()
        
        # Test set/get with TTL
        test_key = f"test:mimir:{int(datetime.now().timestamp())}"
        test_value = {"message": "Hello from Mimir", "timestamp": datetime.now().isoformat()}
        
        # Set with TTL
        success = await redis_manager.set_with_ttl(test_key, test_value, 60)
        if success:
            print("✅ Set with TTL: SUCCESS")
        else:
            print("❌ Set with TTL: FAILED")
            return False
        
        # Get JSON
        retrieved = await redis_manager.get_json(test_key)
        if retrieved and retrieved["message"] == test_value["message"]:
            print("✅ Get JSON: SUCCESS")
        else:
            print("❌ Get JSON: FAILED")
            return False
        
        # Test pipeline
        async with redis_manager.pipeline() as pipe:
            pipe.set(f"{test_key}:1", "value1")
            pipe.set(f"{test_key}:2", "value2")
            pipe.set(f"{test_key}:3", "value3")
            results = pipe.execute()
            
        if results:
            print("✅ Pipeline operations: SUCCESS")
        else:
            print("❌ Pipeline operations: FAILED")
            return False
        
        # Test pattern deletion
        deleted_count = await redis_manager.delete_pattern(f"{test_key}*")
        if deleted_count > 0:
            print(f"✅ Pattern deletion: SUCCESS (deleted {deleted_count} keys)")
        else:
            print("❌ Pattern deletion: FAILED")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Redis operations error: {e}")
        return False

async def test_distribution_service():
    """Test distribution service initialization"""
    print("\n🔄 Testing Distribution Service...")
    
    try:
        from distribution_service import DistributionService
        
        # Create distribution service
        dist_service = DistributionService()
        
        # Test Redis health check
        redis_healthy = await dist_service.is_redis_healthy()
        if redis_healthy:
            print("✅ Distribution service Redis health: SUCCESS")
        else:
            print("⚠️  Distribution service Redis health: FAILED (fallback mode available)")
        
        # Test get distribution status
        test_scene_id = "test-scene-123"
        status = await dist_service.get_distribution_status(test_scene_id)
        
        if "scene_id" in status:
            print("✅ Distribution status check: SUCCESS")
            print(f"   Scene ID: {status['scene_id']}")
            print(f"   Redis available: {status.get('redis_available', False)}")
        else:
            print("❌ Distribution status check: FAILED")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Distribution service import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Distribution service error: {e}")
        return False

async def test_simulated_content_claim():
    """Test simulated content claim flow"""
    print("\n🔄 Testing simulated content claim...")
    
    try:
        from distribution_service import DistributionService
        
        dist_service = DistributionService()
        
        # Test claim for non-existent scene (should handle gracefully)
        test_scene_id = "test-scene-456"
        test_display_id = "test-display-789"
        
        result = await dist_service.claim_next_content(test_scene_id, test_display_id)
        
        if "status" in result:
            print(f"✅ Content claim simulation: SUCCESS")
            print(f"   Status: {result['status']}")
            print(f"   Method: {result.get('method', 'unknown')}")
            
            # If we got an assignment, test acknowledgment
            if result.get("assignment_id"):
                ack_result = await dist_service.acknowledge_assignment(
                    test_scene_id, 
                    test_display_id, 
                    result["assignment_id"], 
                    "test_completed"
                )
                
                if "status" in ack_result:
                    print(f"✅ Assignment acknowledgment: SUCCESS")
                    print(f"   Ack status: {ack_result['status']}")
                else:
                    print("❌ Assignment acknowledgment: FAILED")
        else:
            print("❌ Content claim simulation: FAILED")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Content claim simulation error: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Mimir Redis Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Redis Operations", test_redis_operations),
        ("Distribution Service", test_distribution_service),
        ("Content Claim Simulation", test_simulated_content_claim),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}: EXCEPTION - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Redis integration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    # Set up basic logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
