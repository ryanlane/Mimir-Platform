#!/usr/bin/env python3
"""
Test WebSocket Distribution Events
Tests the new Redis-powered distribution event broadcasting functionality.
"""

import asyncio
import websockets
import json
import requests
import time
from datetime import datetime

# Configuration
API_BASE = "http://oak:5000"  # Production server
WS_URL = "ws://oak:5000/ws"

async def test_websocket_events():
    """Test the new distribution event broadcasting"""
    print("=== Testing WebSocket Distribution Events ===")
    print(f"Connecting to: {WS_URL}")
    
    try:
        # Connect to WebSocket
        async with websockets.connect(WS_URL) as websocket:
            print("✅ WebSocket connected successfully")
            
            # Listen for initial connection event
            initial_message = await websocket.recv()
            initial_data = json.loads(initial_message)
            print(f"📨 Initial connection: {initial_data.get('event', 'unknown')}")
            
            # Set up event listener task
            async def listen_for_events():
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        event_type = data.get('event', 'unknown')
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        
                        if event_type in [
                            'content_assigned', 'content_released', 'lease_renewed',
                            'epoch_started', 'queue_status', 'distribution_performance'
                        ]:
                            print(f"🔔 [{timestamp}] {event_type}: {json.dumps(data.get('data', {}), indent=2)}")
                        else:
                            print(f"📨 [{timestamp}] Other event: {event_type}")
                            
                    except websockets.exceptions.ConnectionClosed:
                        print("🔌 WebSocket connection closed")
                        break
                    except Exception as e:
                        print(f"❌ Error receiving message: {e}")
            
            # Start listening in background
            listen_task = asyncio.create_task(listen_for_events())
            
            print("\n=== Triggering Distribution Events ===")
            
            # Test 1: Get active scenes
            print("\n1. Getting active scenes...")
            response = requests.get(f"{API_BASE}/api/scenes")
            if response.status_code == 200:
                scenes = response.json()
                active_scenes = [s for s in scenes if s.get('is_active')]
                print(f"   Found {len(active_scenes)} active scenes")
                
                if active_scenes:
                    scene_id = active_scenes[0]['id']
                    scene_name = active_scenes[0]['name']
                    print(f"   Using scene: {scene_name} ({scene_id})")
                    
                    # Test 2: Refresh scene content (should trigger epoch_started and queue_status)
                    print("\n2. Refreshing scene content...")
                    refresh_response = requests.post(f"{API_BASE}/api/scenes/{scene_id}/refresh_content")
                    if refresh_response.status_code == 200:
                        print("   ✅ Content refresh triggered")
                        print("   🔍 Watch for: epoch_started, queue_status events")
                    else:
                        print(f"   ❌ Content refresh failed: {refresh_response.status_code}")
                    
                    # Test 3: Get distribution status
                    print("\n3. Getting distribution status...")
                    status_response = requests.get(f"{API_BASE}/api/scenes/{scene_id}/distribution_status")
                    if status_response.status_code == 200:
                        status = status_response.json()
                        print(f"   Distribution mode: {status.get('distribution_mode', 'unknown')}")
                        print(f"   Active leases: {status.get('active_leases', 0)}")
                        print(f"   Queue items: {status.get('queue_status', {}).get('total_items', 0)}")
                    
                    # Test 4: Check display clients for content claiming test
                    print("\n4. Getting display clients...")
                    clients_response = requests.get(f"{API_BASE}/api/display_clients")
                    if clients_response.status_code == 200:
                        clients = clients_response.json()
                        assigned_clients = [c for c in clients if c.get('assigned_scene_id') == scene_id]
                        print(f"   Found {len(assigned_clients)} clients assigned to scene")
                        
                        if assigned_clients:
                            client_id = assigned_clients[0]['id']
                            print(f"   Using client: {client_id}")
                            
                            # Test 5: Simulate content claim (should trigger content_assigned)
                            print("\n5. Simulating content claim...")
                            claim_data = {
                                "client_version": "test-1.0",
                                "capabilities": {"formats": ["image/jpeg", "image/png"]}
                            }
                            claim_response = requests.post(
                                f"{API_BASE}/api/displays/{client_id}/claim_content",
                                json=claim_data
                            )
                            if claim_response.status_code == 200:
                                claim_result = claim_response.json()
                                print("   ✅ Content claim successful")
                                print(f"   Status: {claim_result.get('status')}")
                                print("   🔍 Watch for: content_assigned event")
                                
                                # Test 6: Acknowledge assignment (should trigger content_released)
                                if claim_result.get('assignment_id'):
                                    print("\n6. Acknowledging assignment...")
                                    ack_data = {
                                        "assignment_id": claim_result['assignment_id'],
                                        "status": "displayed",
                                        "details": {"content_id": claim_result.get('content_id')}
                                    }
                                    ack_response = requests.post(
                                        f"{API_BASE}/api/displays/{client_id}/acknowledge",
                                        json=ack_data
                                    )
                                    if ack_response.status_code == 200:
                                        print("   ✅ Assignment acknowledged")
                                        print("   🔍 Watch for: content_released event")
                                    else:
                                        print(f"   ❌ Acknowledgment failed: {ack_response.status_code}")
                            else:
                                print(f"   ❌ Content claim failed: {claim_response.status_code}")
                                print(f"   Response: {claim_response.text}")
                        else:
                            print("   ⚠️  No display clients assigned to scene for testing")
                    
                else:
                    print("   ⚠️  No active scenes found for testing")
            
            print("\n=== Monitoring for Events ===")
            print("Listening for distribution events for 60 seconds...")
            print("Expected events: distribution_performance (every 30s), queue_status")
            
            # Wait for events
            try:
                await asyncio.wait_for(listen_task, timeout=60)
            except asyncio.TimeoutError:
                print("\n⏰ Monitoring timeout reached")
            
            print("\n=== Test Complete ===")
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")

def test_api_availability():
    """Test if the API is available"""
    print("=== Testing API Availability ===")
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is available")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API not available: {e}")
        return False

if __name__ == "__main__":
    print("🧪 WebSocket Distribution Events Test")
    print("=====================================")
    
    # Check API availability first
    if test_api_availability():
        # Run WebSocket test
        asyncio.run(test_websocket_events())
    else:
        print("❌ Cannot run WebSocket tests - API not available")
