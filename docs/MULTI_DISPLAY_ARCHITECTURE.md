# Multi-Display Client Architecture

This document explains the new multi-display client system that allows multiple display clients to connect and receive targeted scene assignments.

## 🏗️ **Architecture Overview**

### **Core Components**

1. **Display Client Registration**: Each display registers with unique capabilities
2. **Scene Assignment**: Scenes can be assigned to specific display clients  
3. **Targeted WebSocket Communication**: Messages sent to specific displays
4. **Dashboard Monitoring**: Admin interface tracks all display clients

### **Database Schema**

The system adds a new `DisplayClient` table:

```sql
-- Display Clients Table
CREATE TABLE display_clients (
    id TEXT PRIMARY KEY,              -- UUID
    name TEXT NOT NULL,               -- "Lobby Display"
    description TEXT,                 -- "Main entrance display"
    location TEXT,                    -- "Building A, Floor 1"
    
    -- Capabilities
    resolution JSON,                  -- [1920, 1080]
    supported_formats JSON,           -- ["jpg", "png", "gif"]
    rotation TEXT DEFAULT 'landscape', -- "landscape" | "portrait"
    
    -- Status
    is_online BOOLEAN DEFAULT FALSE,
    last_seen DATETIME,
    websocket_connection_id TEXT,
    
    -- Assignment
    assigned_scene_id TEXT,           -- FK to scenes.id
    
    -- Configuration
    settings JSON,                    -- Display-specific settings
    tags JSON,                        -- ["lobby", "kiosk", "conference"]
    
    -- Metadata
    created_at DATETIME,
    updated_at DATETIME
);
```

## 🔌 **API Endpoints**

### **Display Client Registration**

**POST** `/api/displays/register`

Register a new display client with its capabilities:

```json
{
  "name": "Conference Room A Display",
  "description": "Main display for conference room A",
  "location": "Building A, Floor 2, Room A203",
  "capabilities": {
    "resolution": [1920, 1080],
    "supported_formats": ["jpg", "png"],
    "rotation": "landscape"
  },
  "tags": ["conference-room", "interactive"]
}
```

**Response:**
```json
{
  "id": "display-uuid-here",
  "name": "Conference Room A Display",
  "description": "Main display for conference room A",
  "location": "Building A, Floor 2, Room A203",
  "is_online": false,
  "last_seen": null,
  "assigned_scene_id": null,
  "assigned_scene_name": null,
  "resolution": [1920, 1080],
  "rotation": "landscape",
  "tags": ["conference-room", "interactive"]
}
```

### **List Display Clients**

**GET** `/api/displays?online_only=true&location=Building A`

**Response:**
```json
[
  {
    "id": "display-uuid-1",
    "name": "Lobby Display",
    "location": "Building A, Floor 1",
    "is_online": true,
    "last_seen": "2025-08-20T15:30:00Z",
    "assigned_scene_id": "lobby-scene",
    "assigned_scene_name": "Lobby Information",
    "resolution": [1920, 1080],
    "rotation": "landscape",
    "tags": ["lobby", "public"]
  }
]
```

### **Scene Assignment**

**POST** `/api/displays/{display_id}/assign_scene`

Assign a scene to a specific display:

```json
{
  "scene_id": "morning-gallery"
}
```

**Response:**
```json
{
  "message": "Scene assignment updated for display Conference Room A Display",
  "assigned_scene": "Morning Gallery",
  "message_sent": true
}
```

### **Scene Activation on Displays**

**POST** `/api/scenes/{scene_id}/activate_on_displays`

Activate a scene on specific displays or all assigned displays:

```json
{
  "display_ids": ["display-uuid-1", "display-uuid-2"]
}
```

## 🔌 **WebSocket Communication**

### **Display Client Connection**

Display clients connect to: `ws://api-server/ws/display/{display_id}`

**Connection Established Event:**
```json
{
  "event": "display_connection_established",
  "data": {
    "displayId": "display-uuid-1",
    "displayName": "Lobby Display",
    "assignedScene": {
      "id": "lobby-scene",
      "name": "Lobby Information",
      "channels": ["weather_channel", "news_channel"]
    },
    "capabilities": {
      "resolution": [1920, 1080],
      "rotation": "landscape",
      "supported_formats": ["jpg", "png"]
    },
    "serverTime": "2025-08-20T15:30:00Z"
  },
  "timestamp": "2025-08-20T15:30:00Z"
}
```

### **Scene Assignment Event**

When a scene is assigned to a display:

```json
{
  "event": "scene_assigned",
  "data": {
    "displayId": "display-uuid-1",
    "sceneId": "evening-gallery",
    "sceneName": "Evening Gallery",
    "previousSceneId": "lobby-scene",
    "timestamp": "2025-08-20T15:30:00Z"
  },
  "timestamp": "2025-08-20T15:30:00Z",
  "sequenceId": 12345
}
```

### **Scene Activation Event**

When a scene is activated on displays:

```json
{
  "event": "scene_activated",
  "data": {
    "sceneId": "morning-gallery",
    "sceneName": "Morning Gallery", 
    "channels": ["weather_channel"],
    "overlay": {
      "overlays": ["date"],
      "position": ["top", "right"]
    },
    "timestamp": "2025-08-20T15:30:00Z"
  },
  "timestamp": "2025-08-20T15:30:00Z",
  "sequenceId": 12346
}
```

## 💻 **Display Client Implementation Example**

### **Python Display Client**

```python
import asyncio
import websockets
import json
import requests
from typing import Dict, Any

class MimirDisplayClient:
    def __init__(self, api_base: str, display_config: Dict[str, Any]):
        self.api_base = api_base
        self.display_config = display_config
        self.display_id = None
        self.websocket = None
        self.current_scene = None
        
    async def register(self):
        """Register this display client with the API"""
        response = requests.post(
            f"{self.api_base}/api/displays/register",
            json=self.display_config
        )
        response.raise_for_status()
        registration_data = response.json()
        self.display_id = registration_data["id"]
        print(f"✅ Registered as display: {self.display_id}")
        return registration_data
        
    async def connect_websocket(self):
        """Connect to the display-specific WebSocket"""
        if not self.display_id:
            raise ValueError("Must register before connecting WebSocket")
            
        ws_url = f"ws://{self.api_base.replace('http://', '')}/ws/display/{self.display_id}"
        
        async with websockets.connect(ws_url) as websocket:
            self.websocket = websocket
            print(f"🔌 Connected to WebSocket: {ws_url}")
            
            async for message in websocket:
                await self.handle_message(json.loads(message))
                
    async def handle_message(self, message: Dict[str, Any]):
        """Handle incoming WebSocket messages"""
        event = message.get("event")
        data = message.get("data", {})
        
        if event == "display_connection_established":
            print("🏠 Display connection established")
            assigned_scene = data.get("assignedScene")
            if assigned_scene:
                self.current_scene = assigned_scene
                print(f"📺 Assigned scene: {assigned_scene['name']}")
                await self.load_scene(assigned_scene)
                
        elif event == "scene_assigned":
            print(f"🎬 New scene assigned: {data.get('sceneName')}")
            # Fetch full scene details and load
            await self.fetch_and_load_scene(data.get("sceneId"))
            
        elif event == "scene_activated":
            print(f"▶️ Scene activated: {data.get('sceneName')}")
            # Update display with activated scene
            await self.activate_scene(data)
            
        elif event == "ping":
            # Respond to server ping
            await self.websocket.send(json.dumps({
                "event": "pong",
                "data": {"timestamp": data.get("timestamp")}
            }))
            
    async def fetch_and_load_scene(self, scene_id: str):
        """Fetch scene details and load on display"""
        response = requests.get(f"{self.api_base}/api/scenes/{scene_id}")
        if response.status_code == 200:
            scene_data = response.json()
            await self.load_scene(scene_data)
            
    async def load_scene(self, scene_data: Dict[str, Any]):
        """Load a scene on this display"""
        print(f"🎨 Loading scene: {scene_data['name']}")
        print(f"📡 Channels: {', '.join(scene_data.get('channels', []))}")
        
        # TODO: Implement actual display rendering logic
        # This would:
        # 1. Generate images for each channel in the scene
        # 2. Composite them according to scene layout
        # 3. Display the result on the physical screen
        
        self.current_scene = scene_data
        
    async def activate_scene(self, activation_data: Dict[str, Any]):
        """Activate/refresh currently assigned scene"""
        if self.current_scene:
            await self.load_scene(self.current_scene)

# Usage Example
async def main():
    display_client = MimirDisplayClient(
        api_base="http://localhost:5000",
        display_config={
            "name": "Lobby Display #1",
            "description": "Main lobby information display",
            "location": "Building A, Main Entrance",
            "capabilities": {
                "resolution": [1920, 1080],
                "supported_formats": ["jpg", "png"],
                "rotation": "landscape"
            },
            "tags": ["lobby", "public", "information"]
        }
    )
    
    # Register the display
    await display_client.register()
    
    # Connect and listen for updates
    await display_client.connect_websocket()

if __name__ == "__main__":
    asyncio.run(main())
```

## 🎛️ **Management Workflows**

### **Setup New Display**

1. **Physical Installation**: Install display hardware at location
2. **Registration**: Run registration script on display client
3. **Scene Assignment**: Use admin dashboard to assign initial scene
4. **Testing**: Verify display receives and shows assigned scene

### **Scene Management**

```bash
# Assign scene to specific display
curl -X POST http://localhost:5000/api/displays/display-uuid-1/assign_scene \
  -H "Content-Type: application/json" \
  -d '{"scene_id": "lobby-information"}'

# Activate scene on multiple displays
curl -X POST http://localhost:5000/api/scenes/emergency-alert/activate_on_displays \
  -H "Content-Type: application/json" \
  -d '{"display_ids": ["display-1", "display-2", "display-3"]}'

# Get all displays by location
curl "http://localhost:5000/api/displays?location=Building A"
```

### **Monitoring**

- **Online Status**: Track which displays are currently connected
- **Scene Assignments**: Monitor what scene each display is showing
- **Message Delivery**: Verify WebSocket messages reach target displays
- **Performance**: Track scene load times and display responsiveness

## 🚀 **Benefits**

### **For Administrators**
- **Centralized Control**: Manage all displays from single API
- **Flexible Targeting**: Send different content to different locations
- **Real-time Updates**: Instant scene changes across the network
- **Status Monitoring**: Track online/offline status of all displays

### **For Display Clients**
- **Automatic Registration**: Self-registration with capability detection
- **Targeted Content**: Receive only relevant scene assignments
- **Efficient Communication**: Direct WebSocket connection per display
- **Graceful Handling**: Automatic reconnection and state recovery

### **For System Integration**
- **RESTful API**: Standard HTTP endpoints for all operations
- **WebSocket Events**: Real-time bidirectional communication
- **JSON Configuration**: Easy integration with existing systems
- **Scalable Architecture**: Support for hundreds of display clients

This multi-display system provides a robust foundation for digital signage networks, interactive kiosks, and distributed display management scenarios.
