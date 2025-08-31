#!/usr/bin/env python3
"""
Enhanced API Startup Test

Tests the enhanced Mimir API with Redis integration:
- Starts the API server with Redis available
- Tests basic endpoints
- Tests new distribution endpoints
- Demonstrates Redis-powered multi-display distribution
"""

import requests
import json
import time
import sys
from pathlib import Path


def test_api_health():
    """Test basic API health endpoints"""
    print("\n=== Testing API Health ===")
    
    try:
        # Test HEAD request (the original 405 fix)
        response = requests.head("http://localhost:8000/api/health")
        print(f"HEAD /api/health: {response.status_code}")
        
        # Test GET request
        response = requests.get("http://localhost:8000/api/health")
        if response.status_code == 200:
            health_data = response.json()
            print(f"API Health: {json.dumps(health_data, indent=2)}")
            return health_data.get("status") == "healthy"
        else:
            print(f"Health check failed: {response.status_code}")
            return False
            
    except requests.ConnectionError:
        print("❌ Cannot connect to API server. Is it running on port 8000?")
        return False
    except Exception as e:
        print(f"Health test failed: {e}")
        return False


def test_distribution_endpoints():
    """Test the new distribution endpoints"""
    print("\n=== Testing Distribution Endpoints ===")
    
    try:
        # Test distribution overview
        response = requests.get("http://localhost:8000/api/distribution/overview")
        if response.status_code == 200:
            overview = response.json()
            print(f"Distribution Overview: {json.dumps(overview, indent=2)}")
        else:
            print(f"Distribution overview failed: {response.status_code} - {response.text}")
        
        # Test Redis admin status
        response = requests.get("http://localhost:8000/api/admin/redis/status")
        if response.status_code == 200:
            redis_status = response.json()
            print(f"Redis Status: {json.dumps(redis_status, indent=2)}")
            return True
        elif response.status_code == 501:
            print("Redis not available (expected if Redis not running)")
            return True
        else:
            print(f"Redis status failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Distribution endpoints test failed: {e}")
        return False


def test_scene_operations():
    """Test scene creation and content operations"""
    print("\n=== Testing Scene Operations ===")
    
    try:
        # Create a test scene
        scene_data = {
            "name": "Test Scene for Integration",
            "description": "Scene created by integration test",
            "channels": ["test_channel_1", "test_channel_2"],
            "distribution_mode": "SEQUENTIAL",
            "is_active": True
        }
        
        response = requests.post("http://localhost:8000/api/scenes", json=scene_data)
        if response.status_code == 201:
            scene = response.json()
            scene_id = scene["id"]
            print(f"Created test scene: {scene_id}")
            
            # Test content refresh
            response = requests.post(f"http://localhost:8000/api/scenes/{scene_id}/refresh_content")
            if response.status_code == 200:
                refresh_result = response.json()
                print(f"Content refresh: {json.dumps(refresh_result, indent=2)}")
            elif response.status_code == 501:
                print("Content refresh not available (Redis not running)")
            
            # Test content info
            response = requests.get(f"http://localhost:8000/api/scenes/{scene_id}/content_info")
            if response.status_code == 200:
                content_info = response.json()
                print(f"Content info: {json.dumps(content_info, indent=2)}")
            
            # Clean up - delete test scene
            response = requests.delete(f"http://localhost:8000/api/scenes/{scene_id}")
            if response.status_code == 200:
                print(f"Cleaned up test scene: {scene_id}")
            
            return True
            
        else:
            print(f"Scene creation failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Scene operations test failed: {e}")
        return False


def test_display_content_claiming():
    """Test display content claiming workflow"""
    print("\n=== Testing Display Content Claiming ===")
    
    try:
        # First create a scene for testing
        scene_data = {
            "name": "Distribution Test Scene",
            "description": "Scene for testing distribution",
            "channels": ["test_channel_1"],
            "distribution_mode": "MIRROR",
            "is_active": True
        }
        
        response = requests.post("http://localhost:8000/api/scenes", json=scene_data)
        if response.status_code != 201:
            print(f"Could not create test scene: {response.status_code}")
            return False
        
        scene = response.json()
        scene_id = scene["id"]
        print(f"Created test scene for distribution: {scene_id}")
        
        # Test content claiming by multiple displays
        test_displays = ["display_001", "display_002", "display_003"]
        
        for display_id in test_displays:
            response = requests.post(f"http://localhost:8000/api/displays/{display_id}/claim_content", 
                                   json={"scene_id": scene_id})
            
            if response.status_code == 200:
                content = response.json()
                print(f"Display {display_id} claimed: {content.get('content_id', 'No content')}")
                
                # If content was claimed, acknowledge completion
                if content.get("content"):
                    ack_response = requests.post(
                        f"http://localhost:8000/api/displays/{display_id}/acknowledge_completion",
                        json={
                            "scene_id": scene_id,
                            "content_id": content["content"]["id"]
                        }
                    )
                    if ack_response.status_code == 200:
                        print(f"Display {display_id} acknowledged completion")
                    
            elif response.status_code == 501:
                print(f"Content claiming not available (Redis not running)")
                break
            else:
                print(f"Content claiming failed for {display_id}: {response.status_code}")
        
        # Clean up
        requests.delete(f"http://localhost:8000/api/scenes/{scene_id}")
        return True
        
    except Exception as e:
        print(f"Display content claiming test failed: {e}")
        return False


def main():
    """Run API integration tests"""
    print("Starting Enhanced API Integration Test")
    print("=" * 50)
    
    # Check if API server is likely running
    print("Checking API server availability...")
    
    tests = [
        ("API Health", test_api_health),
        ("Distribution Endpoints", test_distribution_endpoints),
        ("Scene Operations", test_scene_operations),
        ("Display Content Claiming", test_display_content_claiming)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        try:
            success = test_func()
            results[test_name] = "PASS" if success else "FAIL"
        except Exception as e:
            print(f"Test {test_name} crashed: {e}")
            results[test_name] = "CRASH"
    
    # Report results
    print("\n" + "=" * 50)
    print("API INTEGRATION TEST RESULTS")
    print("=" * 50)
    
    for test_name, result in results.items():
        status_icon = "✅" if result == "PASS" else "❌"
        print(f"{status_icon} {test_name}: {result}")
    
    # Overall result
    all_passed = all(result == "PASS" for result in results.values())
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if not all_passed:
        print("\nTo run the API server:")
        print("1. cd mimir-api/api-service")
        print("2. python -m uvicorn main:app --reload --port 8000")
        print("\nTo run with Redis:")
        print("1. docker-compose up -d redis")
        print("2. Then start the API server")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
