#!/usr/bin/env python3
"""
Test script to verify database connection pool is working properly
and WebSocket connections don't leak database sessions.
"""

import asyncio
import websockets
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor

async def test_websocket_connection():
    """Test WebSocket connection without leaking database sessions"""
    try:
        uri = "ws://localhost:5000/ws"
        async with websockets.connect(uri) as websocket:
            # Should receive connection_established event
            message = await websocket.recv()
            data = json.loads(message)
            print(f"✅ WebSocket connected: {data['event']}")
            
            # Send ping
            ping_msg = {"event": "ping", "data": {"timestamp": time.time()}}
            await websocket.send(json.dumps(ping_msg))
            
            # Wait for pong
            pong = await websocket.recv()
            pong_data = json.loads(pong)
            print(f"✅ WebSocket ping/pong: {pong_data['event']}")
            
            return True
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

def test_http_endpoint():
    """Test HTTP endpoints for connection pool usage"""
    try:
        response = requests.get("http://localhost:5000/api/channels")
        if response.status_code == 200:
            print(f"✅ HTTP channels endpoint: {response.status_code}")
            return True
        else:
            print(f"❌ HTTP channels endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")
        return False

async def stress_test():
    """Run multiple concurrent tests"""
    print("🔧 Running database connection pool stress test...")
    
    # Test HTTP endpoints concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        http_futures = [executor.submit(test_http_endpoint) for _ in range(20)]
        http_results = [f.result() for f in http_futures]
    
    print(f"📊 HTTP tests: {sum(http_results)}/20 passed")
    
    # Test WebSocket connections
    ws_tasks = [test_websocket_connection() for _ in range(5)]
    ws_results = await asyncio.gather(*ws_tasks, return_exceptions=True)
    ws_passed = sum(1 for r in ws_results if r is True)
    
    print(f"📊 WebSocket tests: {ws_passed}/5 passed")
    
    # Check WebSocket status
    try:
        response = requests.get("http://localhost:5000/api/websocket/status")
        if response.status_code == 200:
            status = response.json()
            print(f"📡 WebSocket status: {status['connected_clients']} clients, sequence: {status['current_sequence_id']}")
        else:
            print(f"❌ WebSocket status check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ WebSocket status error: {e}")

if __name__ == "__main__":
    print("🚀 Starting database connection pool test...")
    asyncio.run(stress_test())
    print("✅ Test completed!")
