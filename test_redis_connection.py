#!/usr/bin/env python3
"""
Quick Redis Connection Test

Test if Redis is accessible from the API environment.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, '.')

try:
    import redis
    print("✅ Redis library imported successfully")
    
    # Test basic connection
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    result = r.ping()
    print(f"✅ Redis PING successful: {result}")
    
    # Test set/get
    r.set('test_key', 'test_value')
    value = r.get('test_key')
    print(f"✅ Redis set/get test: {value}")
    
    # Cleanup
    r.delete('test_key')
    print("✅ All Redis tests passed!")
    
except ImportError as e:
    print(f"❌ Redis import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    sys.exit(1)
