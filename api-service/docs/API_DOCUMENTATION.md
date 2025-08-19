# Mimir Platform API Documentation

**Version:** 1.1  
**Last Updated:** August 19, 2025  
**Base URL:** `http://localhost:5000`  

---

## Table of Contents

1. [Overview](#overview)
2. [Core API Endpoints](#core-api-endpoints)
3. [Scene Management](#scene-management)
4. [Channel System](#channel-system)
5. [Overlay System](#overlay-system)
6. [Display Management](#display-management)
7. [WebSocket Real-time Updates](#websocket-real-time-updates)
8. [Error Handling](#error-handling)
9. [Response Formats](#response-formats)
10. [Examples](#examples)

---

## Overview

The Mimir Platform provides a RESTful API for managing ambient display scenes, channels, overlays, and content. The API is built with FastAPI and follows REST conventions with JSON request/response bodies.

### Base URLs

- **Main API:** `http://localhost:5000/api`

### Content Types

- **Request:** `application/json` (for JSON payloads), `multipart/form-data` (for file uploads)
- **Response:** `application/json`

### Pagination

All list endpoints support pagination using query parameters:
- **`limit`** (integer, optional): Maximum number of items to return (1-100, default: 20)
- **`offset`** (integer, optional): Number of items to skip for pagination (default: 0)

All paginated responses include a `meta` object with pagination information:
```json
{
  "meta": {
    "total": 42,
    "limit": 20,
    "offset": 0
  }
}
```

### Naming Conventions

The API uses **camelCase** for property names to be React/JavaScript-friendly:
- `settingsType` instead of `settings_type`
- `lastUpdate` instead of `last_update`
- `currentScene` instead of `current_scene`
- `backgroundColor` instead of `background_color`

---


## Core API Endpoints

### System Information

#### GET `/api/channels`
List all discovered channels with their configuration and status.

**Query Parameters:**
- `limit` (integer, optional): Maximum number of items to return (1-100, default: 20)
- `offset` (integer, optional): Number of items to skip (default: 0)

**Response:**
```json
{
  "channels": [
    {
      "id": "weather_channel",
      "name": "Weather Display",
      "description": "Shows current weather conditions",
      "relLogoImagePath": "static/logo.png",
      "version": "1.0.0",
      "settingsType": "simple",      
      "status": {
        "lastUpdate": "2025-08-18T10:30:00Z",
        "lastError": null,
        "usingFallback": false
      }
    }
  ],
  "meta": {
    "total": 2,
    "limit": 20,
    "offset": 0
  }
}
```

#### GET `/api/channels/{channel_id}/config`
Get channel configuration schema for UI generation.

**Parameters:**
- `channel_id` (string): Channel identifier

**Response:**
```json
{
  "name": "Weather Display",
  "description": "Shows current weather conditions",
  "settingsType": "simple",
  "settings": {
    "api_key": {
      "type": "string",
      "required": true,
      "secret": true,
      "label": "API Key"
    },
    "location": {
      "type": "string", 
      "required": true,
      "default": "New York",
      "label": "Location"
    }
  }
}
```

#### GET `/api/channels/{channel_id}/settings`
Get current settings values for a channel.

**Parameters:**
- `channel_id` (string): Channel identifier

**Response:**
```json
{
  "settings": {
    "api_key": "***hidden***",
    "location": "San Francisco"
  }
}
```

#### POST `/api/channels/{channel_id}/settings`
Update channel settings.

**Parameters:**
- `channel_id` (string): Channel identifier

**Request Body:**
```json
{
  "api_key": "your_api_key_here",
  "location": "London"
}
```

**Response:**
```json
{
  "message": "Settings updated successfully"
}
```

#### POST `/api/channels/{channel_id}/image_request`
Request a new image from channel
**Request Body:**
```json
{
  "resolution": [800,600],
  "orientation": "landscape"
}
```

**Parameters:**
- `channel_id` (string): Channel identifier

**Response:**
```json
{
  "success": true,
  "imagePath": "/channels/weather_channel/current.jpg",
  "message": "Test image generated successfully"
}
      "hasOverlays": false,
      "overlays": []
    },
    {
      "id": "weather_channel",
      "name": "Weather Channel",
      "description": "Current weather by location",
      "current_image": "static/current.jpg",
      "hasManagement": true,
      "hasOverlays": true,
      "overlays": ["current_weather", "weekly_forcast", "when_rain"]
    }
  ]
}
```


#### GET `/api/overlays`
List all available overlay plugins. Overlays can exist as stand alone or are included with a channel.

**Query Parameters:**
- `limit` (integer, optional): Maximum number of items to return (1-100, default: 20)
- `offset` (integer, optional): Number of items to skip (default: 0)

**Response:**
```json
{
  "overlays": [
    {
      "id": "date",
      "name": "Date",
      "description": "Shows current date in Month DD, YYYY format",
      "channel": null,
      "pathRoot": "static/"
    },
    {
      "id": "channel_overlay_example",
      "name": "Channel Overlay Example",
      "description": "Shows example data supplied by channel",
      "channel": { "channelId": "example_channel", "channelName": "Example Channel", "overlayPath" : "channel/example_channel/overlay/channel_overlay_example"},
      "pathRoot": null
    }
  ],
  "meta": {
    "total": 2,
    "limit": 20,
    "offset": 0
  }
}
```

---

## Scene Management

### List Scenes

#### GET `/api/scenes`
Retrieve all created scenes.

**Query Parameters:**
- `limit` (integer, optional): Maximum number of items to return (1-100, default: 20)
- `offset` (integer, optional): Number of items to skip (default: 0)

**Response:**
```json
{
  "scenes": [
    {
      "id": "photos-with-date",
      "name": "Photos with Date",
      "channels": ["example_channel"],      
      "overlay": {"overlays":["date"], "position": ["top","right"], "background": true, "backgroundColor": {"red": 0, "green": 0, "blue": 0, "alpha": 10}},
      "schedule": null
    }
  ],
  "meta": {
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

### Create Scene

#### POST `/api/scenes`
Create a new scene.

**Request Body:**
```json
{
  "name": "Evening Gallery",
  "channels": ["example_channel"],
  "overlay": {"overlays":["date"], "position": ["top","right"], "background": true, "backgroundColor": {"red": 0, "green": 0, "blue": 0, "alpha": 10}},
  "schedule": {
    "days": ["mon", "tue", "wed", "thu", "fri"],
    "start": "18:00",
    "end": "22:00"
  }
}
```

**Response:**
```json
{
  "id": "evening-gallery",
  "name": "Evening Gallery",
  "message": "Scene created successfully"
}
```

### Get Scene

#### GET `/api/scenes/{scene_id}`
Retrieve a specific scene by ID.

**Parameters:**
- `scene_id` (string): Scene identifier

**Response:**
```json
{
  "id": "evening-gallery",
  "name": "Evening Gallery",
  "channels": ["example_channel"],
  "image_fit": "cover",
  "overlays": ["date"],
  "schedule": {
    "days": ["mon", "tue", "wed", "thu", "fri"],
    "start": "18:00",
    "end": "22:00"
  },
  "theme": null
}
```

### Update Scene

#### PUT `/api/scenes/{scene_id}`
Update an existing scene.

**Parameters:**
- `scene_id` (string): Scene identifier

**Request Body:**
```json
{
  "name": "Updated Evening Gallery",
  "channels": ["example_channel"],
  "image_fit": "contain",
  "overlays": ["date"],
}
```

**Response:**
```json
{
  "id": "evening-gallery",
  "name": "Updated Evening Gallery",
  "message": "Scene updated successfully"
}
```

### Delete Scene

#### DELETE `/api/scenes/{scene_id}`
Delete a scene.

**Parameters:**
- `scene_id` (string): Scene identifier

**Response:**
```json
{
  "message": "Scene evening-gallery deleted successfully"
}
```

### Scene Activation

#### POST `/api/scenes/{scene_id}/activate`
Activate a scene (makes it current and starts auto-updating).

**Parameters:**
- `scene_id` (string): Scene identifier

**Response:**
```json
{
  "message": "Scene evening-gallery activated successfully"
}
```

#### POST `/api/scenes/{scene_id}/deactivate`
Deactivate a scene (stops auto-updating).

**Parameters:**
- `scene_id` (string): Scene identifier

**Response:**
```json
{
  "message": "Scene evening-gallery deactivated successfully"
}
```

#### POST `/api/scenes/{scene_id}/display`
Display a scene on the e-ink display (one-time rendering).

**Parameters:**
- `scene_id` (string): Scene identifier

**Response:**
```json
{
  "message": "Scene evening-gallery displayed successfully"
}
```

---

## Channel System

### Channel Configuration

Channels are self-contained modules discovered via `config.json` files in the `channels/` directory. Each channel generates images on-demand when requested by the scene engine.

#### Channel Discovery

The platform automatically discovers channels by scanning for:
- `channels/{channel_name}/config.json` - Channel configuration
- `channels/{channel_name}/channel.py` - Python implementation
- `channels/{channel_name}/placeholder.jpg` - Default/fallback image

#### Channel Configuration Schema

```json
{
  "name": "Weather Display",
  "description": "Shows current weather conditions",
  "update_schedule": {
    "unit": "minutes",
    "duration": 15
  },
  "placeholder_image": "placeholder.jpg",
  "current_image": "current.jpg",
  "settings_type": "simple",
  "settings": {
    "api_key": {"type": "string", "required": true, "secret": true},
    "location": {"type": "string", "required": true, "default": "New York"}
  }
}
```

#### Image Generation API

Channels implement a standardized interface:

```python
async def render_image(
    resolution: tuple[int, int], 
    orientation: str, 
    settings: dict
) -> str:
    """Generate image and return relative path"""
```

#### Error Handling

- **Generation Fails**: Use last successful cached image
- **No Cache**: Use placeholder.jpg from channel
- **No Placeholder**: Show error state in console UI

#### Settings Types

- **Simple**: Platform generates UI from JSON schema
- **Complex**: Channel provides custom management interface

---


## Display Management

### Display Status

#### GET `/api/display/status`
Get current display hardware status and active scene information.

**Response:**
```json
{
  "hardware": {
    "type": "mock",
    "resolution": [800, 600],
    "available": true
  },
  "currentScene": "evening-gallery",
  "currentImage": {
    "filename": "current.jpg",
    "path": "/static/display/",
    "width": 1920,
    "height": 1080,
    "uploadedAt": "2025-08-17T10:30:00"
  },
  "resolution": [800, 600]
}
```

### Clear Display

#### POST `/api/display/clear`
Clear the display (remove current content).

**Response:**
```json
{
  "success": true
}
```

---

## WebSocket Real-time Updates

The API provides WebSocket support for real-time updates across all connected clients. This enables live synchronization of scene changes, activations, and other events.

### WebSocket Connection

#### WS `/ws`
Establish a WebSocket connection for real-time updates with enhanced features.

**Connection URL:** `ws://localhost:5000/ws`

**Enhanced Features:**
- **Full State Broadcast** - Complete application state sent on connection
- **Sequence IDs** - Message ordering and duplicate detection
- **Heartbeat/Ping-Pong** - Connection health monitoring
- **Enhanced Event Data** - Rich context and previous state information
- **Error Broadcasting** - Real-time error notifications
- **Channel Status Updates** - Live channel monitoring

**Connection Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:5000/ws');
let lastSequenceId = 0;

ws.onopen = function(event) {
    console.log('WebSocket connected');
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    // Track sequence for state management
    if (message.sequenceId) {
        lastSequenceId = message.sequenceId;
    }
    
    // Handle different event types
    switch(message.event) {
        case 'connection_established':
            // Initialize app with full state
            initializeAppState(message.data.currentState);
            break;
        case 'scene_activated':
            updateSceneUI(message.data);
            break;
        case 'channel_status_update':
            updateChannelStatus(message.data);
            break;
        case 'ping':
            // Respond to server ping
            ws.send(JSON.stringify({
                event: 'pong',
                data: { timestamp: message.data.timestamp }
            }));
            break;
        // ... handle other events
    }
};

// Request state sync if needed
function requestStateSync() {
    ws.send(JSON.stringify({
        event: 'state_sync_request',
        data: { lastKnownSequenceId: lastSequenceId }
    }));
}
```

### Event Types

All WebSocket messages follow this enhanced format:
```json
{
  "event": "event_type",
  "data": { 
    /* event-specific data */,
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-19T10:30:00.000Z"
    }
  },
  "timestamp": "2025-08-19T10:30:00.000Z",
  "sequenceId": 12345
}
```

#### Connection Events

**`connection_established`**
Sent immediately when WebSocket connection is established with complete application state.
```json
{
  "event": "connection_established",
  "data": {
    "connectionId": "conn_1692451800.123",
    "currentState": {
      "displayStatus": {
        "currentScene": "morning-gallery",
        "currentSceneName": "Morning Gallery",
        "hardware": {
          "type": "mock",
          "resolution": [800, 600],
          "available": true
        },
        "resolution": [800, 600]
      },
      "activeScenes": ["morning-gallery"],
      "allScenes": [
        {
          "id": "morning-gallery",
          "name": "Morning Gallery", 
          "isActive": true,
          "channels": ["weather_channel"]
        }
      ],
      "channels": [
        {
          "id": "weather_channel",
          "name": "Weather Display",
          "status": {
            "lastUpdate": "2025-08-19T10:30:00Z",
            "lastError": null,
            "usingFallback": false
          }
        }
      ]
    },
    "serverInfo": {
      "version": "1.0",
      "connectedClients": 3,
      "serverTime": "2025-08-19T10:30:00Z"
    }
  },
  "timestamp": "2025-08-19T10:30:00.000Z",
  "sequenceId": 1
}
```

**`ping` / `pong`**
Heartbeat mechanism for connection health monitoring.
```json
{
  "event": "ping",
  "data": {
    "timestamp": "2025-08-19T10:30:00.000Z"
  },
  "timestamp": "2025-08-19T10:30:00.000Z"
}
```

#### Scene Events

**`scene_activated`**
```json
{
  "event": "scene_activated",
  "data": {
    "sceneId": "morning-gallery",
    "sceneName": "Morning Gallery",
    "channels": ["weather_channel"],
    "previousScene": "evening-display",
    "previousSceneName": "Evening Display",
    "displayUpdate": {
      "resolution": [800, 600],
      "hardware": {
        "type": "mock",
        "available": true
      }
    },
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-19T10:30:00.000Z"
    }
  },
  "timestamp": "2025-08-19T10:30:00.000Z",
  "sequenceId": 12345
}
```

**`scene_deactivated`**
```json
{
  "event": "scene_deactivated", 
  "data": {
    "sceneId": "morning-gallery",
    "sceneName": "Morning Gallery",
    "channels": ["weather_channel"],
    "displayUpdate": {
      "currentScene": null,
      "currentSceneName": null
    },
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-19T10:30:00.000Z"
    }
  },
  "timestamp": "2025-08-19T10:30:00.000Z",
  "sequenceId": 12346
}
```

**`scene_created`**
```json
{
  "event": "scene_created",
  "data": {
    "sceneId": "new-scene",
    "sceneName": "New Scene",
    "channels": ["weather_channel"]
  },
  "timestamp": "2025-08-19T10:30:00.000Z"
}
```

**`scene_updated`**
```json
{
  "event": "scene_updated",
  "data": {
    "sceneId": "morning-gallery",
    "sceneName": "Updated Morning Gallery",
    "channels": ["weather_channel", "photos"]
  },
  "timestamp": "2025-08-19T10:30:00.000Z"
}
```

**`scene_deleted`**
```json
{
  "event": "scene_deleted",
  "data": {
    "sceneId": "old-scene",
    "sceneName": "Old Scene"
  },
  "timestamp": "2025-08-19T10:30:00.000Z"
}
```

#### Channel Events

**`channel_status_update`**
Real-time channel monitoring and status updates.
```json
{
  "event": "channel_status_update",
  "data": {
    "channelId": "weather_channel",
    "channelName": "Weather Display",
    "status": {
      "active": true,
      "lastUpdate": "2025-08-19T10:30:00Z",
      "lastSettingsUpdate": "2025-08-19T10:30:00Z",
      "usingFallback": false,
      "lastError": null,
      "imageGenerated": true
    },
    "settingsUpdated": true,
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-19T10:30:00.000Z"
    }
  },
  "timestamp": "2025-08-19T10:30:00.000Z",
  "sequenceId": 12347
}
```

#### Error Events

**`error`**
Real-time error notifications with recovery suggestions.
```json
{
  "event": "error",
  "data": {
    "code": "SCENE_ACTIVATION_FAILED",
    "message": "Failed to activate scene: hardware unavailable",
    "context": {
      "sceneId": "evening-gallery",
      "attemptedAction": "activate"
    },
    "recovery": {
      "action": "check_logs",
      "timestamp": "2025-08-19T10:30:00Z"
    },
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-19T10:30:00.000Z"
    }
  },
  "timestamp": "2025-08-19T10:30:00.000Z",
  "sequenceId": 12348
}
```

#### Display Events

**`display_hardware_update`**
Monitor display hardware status changes.
```json
{
  "event": "display_hardware_update",
  "data": {
    "hardware": {
      "type": "mock",
      "available": true,
      "resolution": [800, 600]
    },
    "action": "display_cleared",
    "impact": {
      "currentScene": null,
      "displayActive": false
    },
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-19T10:30:00.000Z"
    }
  },
  "timestamp": "2025-08-19T10:30:00.000Z",
  "sequenceId": 12349
}
```

### WebSocket Status

#### GET `/api/websocket/status`
Get current WebSocket connection information.

**Response:**
```json
{
  "connected_clients": 3,
  "websocket_url": "ws://localhost:5000/ws",
  "current_sequence_id": 12350,
  "features": {
    "full_state_on_connect": true,
    "heartbeat_support": true,
    "enhanced_events": true,
    "error_broadcasting": true,
    "channel_status_updates": true
  }
}
```

### Benefits

- **🚀 Instant State Sync** - Full application state delivered on connection
- **📊 Sequence Tracking** - Message ordering and duplicate detection via sequence IDs
- **💓 Connection Health** - Automatic heartbeat/ping-pong for connection monitoring
- **🔍 Rich Context** - Enhanced event data with previous state and trigger information
- **⚡ Live Updates** - Changes are instantly reflected across all browser tabs
- **👥 Multi-User Support** - Multiple users see changes in real-time
- **🛡️ Better Error Handling** - Real-time error notifications with recovery suggestions
- **📡 Channel Monitoring** - Live status updates for all channels
- **🔄 State Recovery** - Automatic state synchronization on reconnection
- **🎯 Event-Driven** - React to specific events rather than full data refreshes

---

## Error Handling

### HTTP Status Codes

- **200 OK** - Request successful
- **201 Created** - Resource created successfully
- **400 Bad Request** - Invalid request data
- **404 Not Found** - Resource not found
- **500 Internal Server Error** - Server error

### Error Response Format

```json
{
  "detail": "Scene not found"
}
```

### Common Error Scenarios

#### Scene Not Found (404)
```json
{
  "detail": "Scene not found"
}
```

#### Invalid Scene Data (400)
```json
{
  "detail": "Scene name is required"
}
```



---

## Response Formats

### Scene Object
```json
{
  "id": "scene-identifier",
  "name": "Human Readable Name",
  "channels": ["channel_id"],
  "overlay": {
    "overlays": ["overlay_id"],
    "position": ["top", "right"],
    "background": true,
    "backgroundColor": {"red": 0, "green": 0, "blue": 0, "alpha": 10}
  },
  "schedule": {
    "days": ["mon", "tue", "wed"],
    "start": "18:00",
    "end": "22:00"
  },
  "isActive": false
}
```

### Channel Object
```json
{
  "id": "channel_identifier",
  "name": "Channel Name",
  "description": "Channel description",
  "version": "1.0.0",
  "settingsType": "simple",
  "status": {
    "lastUpdate": "2025-08-18T10:30:00Z",
    "lastError": null,
    "usingFallback": false
  }
}
```

---

## Examples

### Complete Scene Creation Workflow

1. **Check available channels:**
```bash
curl -X GET "http://localhost:5000/api/channels?limit=10&offset=0"
```

2. **Create scene:**
```bash
curl -X POST http://localhost:5000/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Morning Gallery",
    "channels": ["example_channel"],
    "overlay": {
      "overlays": ["date"],
      "position": ["top", "right"],
      "background": true,
      "backgroundColor": {"red": 0, "green": 0, "blue": 0, "alpha": 10}
    }
  }'
```

3. **Activate scene:**
```bash
curl -X POST http://localhost:5000/api/scenes/morning-gallery/activate
```


### Display Management

1. **Check display status:**
```bash
curl -X GET http://localhost:5000/api/display/status
```

2. **Display scene immediately:**
```bash
curl -X POST http://localhost:5000/api/scenes/morning-gallery/display
```

3. **Clear display:**
```bash
curl -X POST http://localhost:5000/api/display/clear
```

---


## Changelog

### v1.0 (August 2025)
- Initial API implementation with FastAPI
- SQLite database integration with SQLAlchemy
- Core scene management endpoints
- Channel management with configuration schemas
- Overlay system endpoints
- Display management endpoints
- **WebSocket real-time updates** for live scene synchronization
- Scene activation state tracking (`isActive` field)
- Pagination support for all list endpoints
- React-friendly camelCase property naming
- CORS support for frontend integration
- Error handling standardization
- Sample data initialization

---

## Future Enhancements

### Planned API Features
- **Authentication:** JWT-based auth with device pairing
- **WebSocket API:** Real-time scene updates
- **Batch Operations:** Bulk scene/photo operations
- **Advanced Filtering:** Query parameters for listing endpoints
- **Versioning:** API version headers and backwards compatibility
- **Rate Limiting:** Request throttling and quotas
- **Webhooks:** Event notifications for scene changes

### Plugin API Expansion
- **Channel Plugin API:** Standardized plugin registration
- **Overlays Plugin API:** Enhanced overlay system
- **Configuration Schemas:** Dynamic UI generation
- **Plugin Marketplace:** Discovery and installation

---

This documentation covers the current state of the Mimir Platform API. For the latest updates and additional endpoints, refer to the FastAPI automatic documentation at `http://localhost:5000/docs` when running the server.
