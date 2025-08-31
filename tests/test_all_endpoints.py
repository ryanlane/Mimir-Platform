#!/usr/bin/env python3
"""
Comprehensive Rate Limiting Test for All Endpoints
Tests the rate limiting implementation across all API endpoints
"""

import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

BASE_URL = "http://localhost:5000"

# Test endpoints (prioritizing the most commonly used ones)
TEST_ENDPOINTS = [
    "/api/channels",
    "/api/scenes", 
    "/api/overlays",
    "/api/display/status",
    "/api/websocket/status",
    "/api/channels/manifest",
    "/api/channels/example_channel/config",
    "/api/channels/example_channel/settings"
]

def make_request(endpoint):
    """Make a single request and return response info"""
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        return {
            'endpoint': endpoint,
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'timestamp': time.time()
        }
    except Exception as e:
        return {
            'endpoint': endpoint,
            'error': str(e),
            'timestamp': time.time()
        }

def test_endpoint_rate_limiting(endpoint, num_requests=25):
    """Test rate limiting for a specific endpoint"""
    print(f"\n🎯 Testing endpoint: {endpoint}")
    print(f"📊 Making {num_requests} rapid requests...")
    
    # Make rapid requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request, endpoint) for _ in range(num_requests)]
        responses = [future.result() for future in as_completed(futures)]
    
    # Analyze results
    status_codes = defaultdict(int)
    rate_limited = 0
    successful = 0
    
    for response in responses:
        if 'error' in response:
            print(f"❌ Request error: {response['error']}")
            continue
            
        status_code = response['status_code']
        status_codes[status_code] += 1
        
        if status_code == 429:
            rate_limited += 1
            # Check for rate limit headers
            headers = response['headers']
            retry_after = headers.get('retry-after', 'Not set')
            remaining = headers.get('x-ratelimit-remaining', 'Not set')
            print(f"🛑 Rate limited! Retry-After: {retry_after}, Remaining: {remaining}")
        elif status_code == 200:
            successful += 1
            
    print(f"✅ Successful requests: {successful}")
    print(f"🛑 Rate limited requests: {rate_limited}")
    print(f"📈 Status code distribution: {dict(status_codes)}")
    
    return {
        'endpoint': endpoint,
        'successful': successful,
        'rate_limited': rate_limited,
        'status_codes': dict(status_codes)
    }

def main():
    print("🧪 Comprehensive Rate Limiting Test")
    print("=" * 60)
    print(f"🎯 Base URL: {BASE_URL}")
    print(f"🔢 Testing {len(TEST_ENDPOINTS)} endpoints")
    print(f"⚡ Global limit: 120 requests/minute per IP")
    
    results = []
    
    for endpoint in TEST_ENDPOINTS:
        result = test_endpoint_rate_limiting(endpoint)
        results.append(result)
        time.sleep(1)  # Brief pause between endpoint tests
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY REPORT")
    print("=" * 60)
    
    total_successful = sum(r['successful'] for r in results)
    total_rate_limited = sum(r['rate_limited'] for r in results)
    
    for result in results:
        endpoint = result['endpoint']
        successful = result['successful']
        rate_limited = result['rate_limited']
        protection = "✅ PROTECTED" if rate_limited > 0 else "⚠️  NO RATE LIMITING"
        print(f"{endpoint:35} | Success: {successful:2d} | Limited: {rate_limited:2d} | {protection}")
    
    print("-" * 60)
    print(f"{'TOTALS':35} | Success: {total_successful:2d} | Limited: {total_rate_limited:2d}")
    
    if total_rate_limited > 0:
        print("\n✅ Rate limiting is working! Some requests were blocked.")
    else:
        print("\n⚠️  No rate limiting detected. Either limits are too high or not applied.")

if __name__ == "__main__":
    main()
