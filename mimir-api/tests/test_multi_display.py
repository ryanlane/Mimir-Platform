#!/usr/bin/env python3
"""
Multi-Display Client Test

This script demonstrates how to register a display client and connect to receive
targeted scene assignments from the Mimir API.
"""

import asyncio
import json
import requests
import websockets
import sys
from datetime import datetime

API_BASE = "http://localhost:5000"

class TestDisplayClient:
    def __init__(self, name: str, location: str):
        self.name = name
        self.location = location
        self.display_id = None
        self.current_scene = None
        
    async def register(self):
        """Register this display client"""
        print(f"🔧 Registering display client: {self.name}")
        
        registration_data = {
            "name": self.name,
            "description": f"Test display client for {self.location}",
            "location": self.location,
            "capabilities": {
                "resolution": [1920, 1080],
                "supported_formats": ["jpg", "png"],
                "orientation": "landscape",
                "refresh_rate_hz": 60
            },
            "tags": ["test", "demo"],
            "client_version": "1.0.0"
        }
        
        try:
            response = requests.post(
                f"{API_BASE}/api/displays/register",
                json=registration_data,
                timeout=10
            )
            response.raise_for_status()
            
            registration_result = response.json()
            self.display_id = registration_result["id"]
            
            print(f"✅ Successfully registered!")
            print(f"   Display ID: {self.display_id}")
            print(f"   Name: {registration_result['name']}")
            print(f"   Location: {registration_result['location']}")
            
            return registration_result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Registration failed: {e}")
            return None
    
    async def connect_websocket(self):
        """Connect to display-specific WebSocket"""
        if not self.display_id:
            print("❌ Cannot connect WebSocket: Not registered")
            return
            
        ws_url = f"ws://localhost:5000/ws/display/{self.display_id}"
        print(f"🔌 Connecting to WebSocket: {ws_url}")
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print("✅ WebSocket connected!")
                print("👂 Listening for events...\n")
                
                async for message in websocket:
                    await self.handle_message(json.loads(message))
                    
        except websockets.exceptions.ConnectionRefused:
            print("❌ WebSocket connection refused. Is the server running?")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
    
    async def handle_message(self, message: dict):
        """Handle incoming WebSocket messages"""
        event = message.get("event")
        data = message.get("data", {})
        timestamp = message.get("timestamp", "")
        
        print(f"📨 [{timestamp}] Event: {event}")
        
        if event == "display_connection_established":
            print(f"   🏠 Connection established for: {data.get('displayName')}")
            assigned_scene = data.get("assignedScene")
            if assigned_scene:
                print(f"   📺 Currently assigned scene: {assigned_scene['name']}")
                print(f"   📡 Scene channels: {', '.join(assigned_scene.get('channels', []))}")
                self.current_scene = assigned_scene
            else:
                print("   ⚪ No scene currently assigned")
            
            capabilities = data.get("capabilities", {})
            print(f"   🖥️  Resolution: {capabilities.get('resolution')}")
            print(f"   🔄 Rotation: {capabilities.get('rotation')}")
            
        elif event == "scene_assigned":
            scene_name = data.get("sceneName")
            previous_scene = data.get("previousSceneId")
            print(f"   🎬 New scene assigned: {scene_name}")
            if previous_scene:
                print(f"   ⬅️  Previous scene: {previous_scene}")
            print("   💡 In a real client, this would trigger scene loading...")
            
        elif event == "scene_activated":
            scene_name = data.get("sceneName")
            channels = data.get("channels", [])
            print(f"   ▶️  Scene activated: {scene_name}")
            print(f"   📡 Channels: {', '.join(channels)}")
            print("   💡 In a real client, this would refresh the display...")
            
        elif event == "ping":
            print("   🏓 Ping received, responding with pong...")
            await self.send_pong(data.get("timestamp"))
            
        elif event == "error":
            print(f"   ❌ Error: {data.get('message')}")
            
        else:
            print(f"   ❓ Unknown event type")
            print(f"   📋 Data: {json.dumps(data, indent=2)}")
        
        print()  # Empty line for readability
    
    async def fetch_current_image(self):
        """Fetch the current scene image assigned to this display"""
        if not self.display_id:
            print("❌ Cannot fetch image: Not registered")
            return None
            
        try:
            response = requests.get(
                f"{API_BASE}/api/displays/{self.display_id}/current_image",
                timeout=10
            )
            
            if response.status_code == 404:
                print("📭 No scene assigned to this display")
                return None
                
            response.raise_for_status()
            image_info = response.json()
            
            print(f"🖼️  Current image info:")
            print(f"   Scene: {image_info['scene_name']}")
            print(f"   Resolution: {image_info['resolution']}")
            print(f"   Generated: {image_info['generated_at']}")
            print(f"   Expires in: {image_info['cache_expires_in']} seconds")
            print(f"   Channels: {', '.join(image_info['channels'])}")
            
            return image_info
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch current image: {e}")
            return None
    
    async def get_status(self):
        """Get detailed status for this display"""
        if not self.display_id:
            print("❌ Cannot get status: Not registered")
            return None
            
        try:
            response = requests.get(
                f"{API_BASE}/api/displays/{self.display_id}/status",
                timeout=10
            )
            response.raise_for_status()
            
            status = response.json()
            print(f"📊 Display Status:")
            print(f"   Name: {status['name']}")
            print(f"   Location: {status['location']}")
            print(f"   Online: {status['is_online']}")
            print(f"   Last seen: {status['last_seen']}")
            print(f"   Last image fetch: {status['last_image_fetch']}")
            print(f"   Resolution: {status['capabilities']['resolution']}")
            print(f"   Orientation: {status['capabilities']['orientation']}")
            
            if status['assigned_scene']:
                print(f"   Assigned scene: {status['assigned_scene']['name']}")
                print(f"   Scene channels: {', '.join(status['assigned_scene']['channels'])}")
            else:
                print(f"   Assigned scene: None")
            
            return status
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get status: {e}")
            return None

async def test_multi_display_system():
    """Test the multi-display system"""
    print("🧪 Multi-Display Client Test")
    print("=" * 50)
    
    # Test with multiple display clients
    display_clients = [
        TestDisplayClient("Lobby Display", "Building A - Main Entrance"),
        TestDisplayClient("Conference Room Display", "Building A - Room 203"),
    ]
    
    # Register all displays
    for client in display_clients:
        result = await client.register()
        if not result:
            print(f"❌ Failed to register {client.name}, skipping...")
            continue
        
        print()
    
    # Connect the first display to WebSocket (for demo)
    if display_clients and display_clients[0].display_id:
        print("🔗 Connecting first display to WebSocket for demo...")
        await display_clients[0].connect_websocket()

async def list_displays():
    """List all registered displays"""
    print("📋 Listing all registered displays...")
    
    try:
        response = requests.get(f"{API_BASE}/api/displays", timeout=10)
        response.raise_for_status()
        
        displays = response.json()
        
        if not displays:
            print("   📭 No displays registered")
            return
        
        print(f"   📱 Found {len(displays)} displays:")
        for display in displays:
            status = "🟢 ONLINE" if display["is_online"] else "🔴 OFFLINE"
            scene = display["assigned_scene_name"] or "None"
            print(f"   • {display['name']} ({display['location']}) - {status}")
            print(f"     Scene: {scene}")
            print(f"     ID: {display['id']}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to list displays: {e}")

async def test_image_fetching():
    """Test the image fetching workflow"""
    print("🖼️  Testing Image Fetching Workflow")
    print("-" * 40)
    
    # Create and register a test display
    display_client = TestDisplayClient("Image Test Display", "Test Location")
    
    registration_result = await display_client.register()
    if not registration_result:
        print("❌ Registration failed, cannot test image fetching")
        return
    
    print("\n1️⃣ Getting status before scene assignment...")
    await display_client.get_status()
    
    print("\n2️⃣ Trying to fetch image without scene assignment...")
    await display_client.fetch_current_image()
    
    # Try to assign a scene (if any exist)
    try:
        response = requests.get(f"{API_BASE}/api/scenes", timeout=10)
        if response.status_code == 200:
            scenes = response.json()
            if scenes.get("scenes"):
                scene_id = scenes["scenes"][0]["id"]
                scene_name = scenes["scenes"][0]["name"]
                
                print(f"\n3️⃣ Assigning scene '{scene_name}' to display...")
                assign_response = requests.post(
                    f"{API_BASE}/api/displays/{display_client.display_id}/assign_scene",
                    json={"scene_id": scene_id},
                    timeout=10
                )
                if assign_response.status_code == 200:
                    print("✅ Scene assigned successfully")
                    
                    print("\n4️⃣ Getting status after scene assignment...")
                    await display_client.get_status()
                    
                    print("\n5️⃣ Fetching current image...")
                    await display_client.fetch_current_image()
                else:
                    print(f"❌ Scene assignment failed: {assign_response.status_code}")
            else:
                print("❌ No scenes available for testing")
        else:
            print("❌ Could not fetch scenes for testing")
    except Exception as e:
        print(f"❌ Error during scene assignment test: {e}")

async def simulate_display_client_polling():
    """Simulate a display client polling for updates"""
    print("🔄 Simulating Display Client Polling")
    print("-" * 40)
    
    display_client = TestDisplayClient("Polling Test Display", "Polling Test Location")
    
    registration_result = await display_client.register()
    if not registration_result:
        print("❌ Registration failed")
        return
    
    print("🔄 Starting polling simulation (will poll 3 times)...")
    
    for i in range(3):
        print(f"\n📡 Poll #{i+1}")
        
        # Check status
        status = await display_client.get_status()
        
        if status and status.get('assigned_scene'):
            # Fetch current image
            image_info = await display_client.fetch_current_image()
            
            if image_info:
                print(f"   ✅ Image fetched successfully")
                print(f"   📏 Image resolution: {image_info['resolution']}")
                print(f"   ⏱️  Cache expires in: {image_info['cache_expires_in']}s")
            else:
                print(f"   ❌ No image available")
        else:
            print(f"   📭 No scene assigned, nothing to fetch")
        
        if i < 2:  # Don't sleep after the last iteration
            print(f"   😴 Waiting 5 seconds before next poll...")
            await asyncio.sleep(5)

async def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            await list_displays()
        elif command == "test":
            await test_multi_display_system()
        elif command == "image":
            await test_image_fetching()
        elif command == "poll":
            await simulate_display_client_polling()
        else:
            print(f"❌ Unknown command: {command}")
            print("Available commands: list, test, image, poll")
    else:
        print("🎛️ Multi-Display System Demo")
        print("Commands:")
        print("  python test_multi_display.py list    - List all displays")
        print("  python test_multi_display.py test    - Full test with WebSocket")
        print("  python test_multi_display.py image   - Test image fetching")
        print("  python test_multi_display.py poll    - Simulate polling behavior")

if __name__ == "__main__":
    asyncio.run(main())
