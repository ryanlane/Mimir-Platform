#!/usr/bin/env python3
"""
Redis Diagnostic Script
Helps troubleshoot Redis connection and status endpoint issues.
"""

import requests
import json
import sys

API_BASE = "http://oak:5000"

def test_basic_health():
    """Test basic API health"""
    print("=== Testing Basic API Health ===")
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"Error Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return None

def test_redis_status():
    """Test Redis status endpoint"""
    print("\n=== Testing Redis Status Endpoint ===")
    try:
        response = requests.get(f"{API_BASE}/api/admin/redis/status", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Redis Status Success:")
            print(json.dumps(data, indent=2))
            return data
        elif response.status_code == 501:
            print("⚠️  Redis not available (501)")
            print(f"Response: {response.text}")
        elif response.status_code == 500:
            print("❌ Internal server error (500)")
            print(f"Response: {response.text}")
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
            
        return None
    except Exception as e:
        print(f"❌ Redis status failed: {e}")
        return None

def test_simple_redis_check():
    """Test a simpler Redis-related endpoint"""
    print("\n=== Testing Simple Redis Check ===")
    try:
        # Try to get scenes (which should work regardless of Redis)
        response = requests.get(f"{API_BASE}/api/scenes", timeout=10)
        print(f"Scenes endpoint - Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Basic database operations working")
        else:
            print(f"⚠️  Database issues: {response.text}")
            
    except Exception as e:
        print(f"❌ Scenes check failed: {e}")

def test_distribution_endpoints():
    """Test distribution-related endpoints"""
    print("\n=== Testing Distribution Endpoints ===")
    
    # Test distribution overview
    try:
        response = requests.get(f"{API_BASE}/api/admin/distribution/overview", timeout=10)
        print(f"Distribution overview - Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Redis Available: {data.get('redis_available', 'unknown')}")
            print(f"Distribution Available: {data.get('distribution_available', 'unknown')}")
        elif response.status_code == 501:
            print("⚠️  Distribution service not available")
        else:
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Distribution overview failed: {e}")

def main():
    print("🔍 Redis Diagnostic Tool")
    print("=" * 50)
    
    # Test basic health first
    health_data = test_basic_health()
    
    if health_data:
        print(f"\n📊 Health Summary:")
        print(f"   Database: {health_data.get('database', {}).get('healthy', 'unknown')}")
        print(f"   Redis: {health_data.get('redis', {}).get('healthy', 'unknown')}")
        print(f"   Overall: {health_data.get('healthy', 'unknown')}")
    
    # Test Redis status endpoint
    test_redis_status()
    
    # Test other endpoints
    test_simple_redis_check()
    test_distribution_endpoints()
    
    print("\n" + "=" * 50)
    print("🔧 Troubleshooting Tips:")
    print("1. If Redis status returns 501 - Redis manager not imported properly")
    print("2. If Redis status returns 500 - Redis connection issues")
    print("3. Check service logs: sudo journalctl -u mimir-api.service -f")
    print("4. Check Redis container: docker ps | grep redis")
    print("5. Test Redis directly: redis-cli -h localhost -p 6379 ping")

if __name__ == "__main__":
    main()
