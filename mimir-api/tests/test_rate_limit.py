#!/usr/bin/env python3
"""
Quick test script to validate rate limiting is working
"""
import requests
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor

def make_request(url, request_num):
    """Make a single request and return the result"""
    try:
        response = requests.get(url, timeout=5)
        return {
            'request_num': request_num,
            'status_code': response.status_code,
            'data': response.json() if response.status_code != 200 else None
        }
    except requests.RequestException as e:
        return {
            'request_num': request_num,
            'status_code': 'ERROR',
            'data': str(e)
        }

def test_rate_limiting():
    base_url = "http://localhost:5000"
    endpoint = "/api/channels"  # Use single endpoint for testing
    
    print("🧪 Testing Rate Limiting with Rapid Requests...")
    print(f"📊 Limit: 120 requests/minute")
    print(f"🎯 Testing endpoint: {endpoint}")
    print("=" * 60)
    
    # Make 130 requests rapidly to exceed the limit
    num_requests = 130
    print(f"🚀 Making {num_requests} rapid requests...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(num_requests):
            future = executor.submit(make_request, f"{base_url}{endpoint}", i+1)
            futures.append(future)
            time.sleep(0.05)  # Small delay to avoid overwhelming
        
        # Collect results
        results = []
        for future in futures:
            results.append(future.result())
    
    # Analyze results
    success_count = sum(1 for r in results if r['status_code'] == 200)
    rate_limited_count = sum(1 for r in results if r['status_code'] == 429)
    error_count = sum(1 for r in results if r['status_code'] not in [200, 429])
    
    print(f"\n📊 Results:")
    print(f"  ✅ Successful requests: {success_count}")
    print(f"  🛑 Rate limited (429): {rate_limited_count}")
    print(f"  ❌ Errors: {error_count}")
    
    # Show first few rate limited responses
    rate_limited_responses = [r for r in results if r['status_code'] == 429]
    if rate_limited_responses:
        print(f"\n🛑 Sample rate limit response:")
        sample = rate_limited_responses[0]
        if sample['data']:
            print(f"     Error: {sample['data'].get('error', 'N/A')}")
            print(f"     Limit: {sample['data'].get('limit', 'N/A')}")
            print(f"     Current requests: {sample['data'].get('current_requests', 'N/A')}")
            print(f"     Retry after: {sample['data'].get('retry_after', 'N/A')} seconds")
    
    if rate_limited_count > 0:
        print(f"\n✅ Rate limiting is WORKING! 🎉")
    else:
        print(f"\n⚠️  Rate limiting might not be active or limit is too high")
    
    print("\n" + "=" * 60)
    print("🏁 Rate limiting test completed")

if __name__ == "__main__":
    test_rate_limiting()
