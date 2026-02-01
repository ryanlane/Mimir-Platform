#!/usr/bin/env python3
"""
Test script to verify CORS configuration is working correctly.
This simulates the browser CORS check that was failing before.
"""

import requests
import sys

def test_cors_preflight(origin, endpoint):
    """Test CORS preflight request"""
    print(f"\n🧪 Testing CORS preflight for origin: {origin}")
    print(f"📍 Endpoint: {endpoint}")
    
    headers = {
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type,Authorization'
    }
    
    try:
        response = requests.options(endpoint, headers=headers, timeout=5)
        print(f"✅ Status: {response.status_code}")
        
        # Check CORS headers
        cors_headers = {}
        for header in ['access-control-allow-origin', 'access-control-allow-credentials', 
                      'access-control-allow-methods', 'access-control-allow-headers',
                      'access-control-max-age']:
            value = response.headers.get(header)
            if value:
                cors_headers[header] = value
                print(f"  {header}: {value}")
        
        # Validate CORS compliance
        origin_header = cors_headers.get('access-control-allow-origin')
        credentials_header = cors_headers.get('access-control-allow-credentials')
        
        if origin_header == '*' and credentials_header == 'true':
            print("❌ CORS VIOLATION: Wildcard origin with credentials=true")
            return False
        elif origin_header == origin and credentials_header == 'true':
            print("✅ CORS COMPLIANT: Explicit origin with credentials")
            return True
        elif origin_header == origin:
            print("✅ CORS OK: Explicit origin (no credentials)")
            return True
        else:
            print(f"⚠️  CORS WARNING: Unexpected configuration")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_actual_request(origin, endpoint):
    """Test actual API request with credentials"""
    print(f"\n🔥 Testing actual request with credentials")
    
    headers = {
        'Origin': origin,
        'Content-Type': 'application/json'
    }
    
    try:
        # Test a simple GET request
        response = requests.get(endpoint, headers=headers, timeout=5)
        print(f"✅ Actual request status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API request successful")
            return True
        else:
            print(f"⚠️  API returned status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Actual request failed: {e}")
        return False

def main():
    """Run CORS tests"""
    server_url = "http://oak:5000"
    test_origins = [
        "http://localhost:3000",
        "http://oak:3000", 
        "http://127.0.0.1:3000",
        "http://badorigin.com"  # This should fail
    ]
    
    print("🧪 CORS Configuration Test Suite")
    print("=" * 50)
    
    all_tests_passed = True
    
    for origin in test_origins:
        # Test preflight
        preflight_ok = test_cors_preflight(origin, f"{server_url}/api/channels")
        
        # Test actual request (only for allowed origins)
        if origin != "http://badorigin.com":
            actual_ok = test_actual_request(origin, f"{server_url}/api/channels")
        else:
            actual_ok = True  # Skip actual test for bad origin
            
        if not preflight_ok:
            all_tests_passed = False
            
        print("-" * 30)
    
    print(f"\n🎯 Overall result: {'✅ PASSED' if all_tests_passed else '❌ FAILED'}")
    return 0 if all_tests_passed else 1

if __name__ == "__main__":
    sys.exit(main())
