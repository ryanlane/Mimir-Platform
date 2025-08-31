# Mimir Platform API - Frontend Reference

**Version:** v2.4  
**Base URL:** `http://your-server:5000`  
**Date:** August 21, 2025

## 📋 **Quick Reference**

### Core Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/channels` | List all available channels |
| `GET` | `/api/channels/manifest` | Get UI manifests for React plugin loader |
| `GET` | `/api/scenes` | List scenes with pagination |
| `GET` | `/api/displays` | List registered display clients |
| `WebSocket` | `/ws` | Real-time updates |

---

## 🔌 **Channel System v2.4**

### Channel Discovery & Metadata

#### `GET /api/channels`
List all discovered channels with metadata and status.

```javascript
// Response
[
  {
    "id": "com.epaperframe.photoframe",
    "name": "Photo Frame Channel", 
    "description": "Advanced photo display with slideshow capabilities",
    "version": "2.0.0",
    "schemaVersion": "2.4",
    "permissions": ["read:photos"],
    "hasUI": true,
    "hasAssets": true,
    "channelDir": "/channels/photo_frame"
  }
]
```

#### `GET /api/channels/manifest`
**🎯 React Plugin Loader** - Get UI-aware manifests for dynamic component loading.

```javascript
// Response - Array of UI-capable channels
[
  {
    "id": "com.epaperframe.photoframe",
    "name": "Photo Frame Channel",
    "version": "2.0.0",
    "ui": [
      {
        "element": "x-photoframe-config",
        "moduleUrl": "/api/channels/com.epaperframe.photoframe/ui/config.esm.js",
        "styleUrl": "/api/channels/com.epaperframe.photoframe/ui/styles.css",
        "slots": ["dashboard.settings", "display.config"],
        "renderMode": "element",
        "integrity": {
          "module": "sha384-...",
          "style": "sha384-..."
        }
      }
    ],
    "assets": [
      {
        "name": "logo",
        "url": "/api/channels/com.epaperframe.photoframe/assets/logo.svg"
      }
    ]
  }
]
```

### Channel Configuration & Settings

#### `GET /api/channels/{channel_id}/config`
Get raw channel configuration (config.json).

#### `GET /api/channels/{channel_id}/settings`
Get current channel settings with defaults merged.

#### `POST /api/channels/{channel_id}/settings`
Update channel settings with validation.

```javascript
// Request body
{
  "poll_interval": 300,
  "image_choice": "family_photos",
  "slideshow_duration": 10
}

// Response  
{
  "success": true,
  "settings": {
    "poll_interval": 300,
    "image_choice": "family_photos", 
    "slideshow_duration": 10
  },
  "changes_detected": true
}
```

### Channel Testing & Health

#### `POST /api/channels/{channel_id}/test`
Run channel test functionality.

#### `GET /api/channels/{channel_id}/health`
Get channel health status.

---

## 🎬 **Scene Management**

### Scene CRUD Operations

#### `GET /api/scenes`
List scenes with pagination.

**Query Parameters:**
- `limit` (int): Max results per page (1-100, default: 20)
- `offset` (int): Number of items to skip (default: 0)

```javascript
// Response
{
  "scenes": [
    {
      "id": 1,
      "name": "Living Room Display",
      "description": "Photo slideshow for living room",
      "channelId": "com.epaperframe.photoframe",
      "channelName": "Photo Frame Channel",
      "isActive": true,
      "createdAt": "2025-08-21T10:00:00",
      "updatedAt": "2025-08-21T15:30:00"
    }
  ],
  "pagination": {
    "total": 5,
    "limit": 20,
    "offset": 0,
    "hasMore": false
  }
}
```

#### `POST /api/scenes`
Create a new scene.

```javascript
// Request
{
  "name": "Kitchen Display",
  "description": "Weather and family photos",
  "channelId": "com.epaperframe.photoframe"
}
```

#### `GET /api/scenes/{scene_id}`
Get specific scene details.

#### `PUT /api/scenes/{scene_id}`
Update scene configuration.

#### `DELETE /api/scenes/{scene_id}`
Delete a scene.

### Scene Activation

#### `POST /api/scenes/{scene_id}/activate`
Activate a scene (deactivates others).

#### `POST /api/scenes/{scene_id}/deactivate`
Deactivate a scene.

---

## 📺 **Display Management**

### Multi-Display Architecture

#### `GET /api/displays`
List all registered display clients.

```javascript
// Response
[
  {
    "id": "display-001",
    "name": "Living Room TV",
    "description": "Main family display",
    "location": "Living Room",
    "isOnline": true,
    "lastSeen": "2025-08-21T15:45:00",
    "assignedSceneId": 1,
    "assignedSceneName": "Family Photos",
    "resolution": [1920, 1080],
    "orientation": "landscape",
    "tags": ["main", "family"],
    "clientVersion": "1.0.0"
  }
]
```

#### `POST /api/displays/register`
Register a new display client.

```javascript
// Request
{
  "name": "Kitchen Display",
  "description": "Compact kitchen screen",
  "location": "Kitchen",
  "capabilities": {
    "resolution": [1024, 768],
    "supported_formats": ["jpg", "png"],
    "orientation": "landscape",
    "refresh_rate_hz": 30
  },
  "tags": ["kitchen", "compact"],
  "client_version": "1.0.0"
}
```

#### `PUT /api/displays/{display_id}`
Update display configuration.

#### `DELETE /api/displays/{display_id}`
Unregister a display client.

### Scene Assignment

#### `POST /api/displays/{display_id}/assign-scene`
Assign a scene to a display.

```javascript
// Request
{
  "sceneId": 1
}
```

#### `POST /api/displays/{display_id}/unassign-scene`
Remove scene assignment from display.

### Image Generation & Retrieval

#### `GET /api/displays/{display_id}/current-image`
**🎯 Display Client Polling** - Get current image with change detection.

**Headers:**
- `If-None-Match`: ETag for conditional requests (returns 304 if unchanged)

```javascript
// Response
{
  "imageUrl": "/api/displays/{display_id}/current_image_file",
  "imagePath": "/generated/displays/display_001_scene_1234567890.jpg",
  "resolution": [1920, 1080],
  "generatedAt": "2025-08-21T15:45:00",
  "channels": ["com.epaperframe.photoframe"],
  "cacheExpiresIn": 300,
  "lastModified": "2025-08-21T15:45:00",
  "contentHash": "a1b2c3d4e5f67890",
  "changeToken": "f7e8d9c6",
  "fileSize": 245760,
  "fileExists": true
}

// 304 Not Modified (when using If-None-Match)
// Empty body, check ETag header for current change token
```

#### `GET /api/displays/{display_id}/current_image_file`
Direct image file download (binary response).

#### `POST /api/displays/{display_id}/generate-image`
Force image regeneration for display.

---

## 🚀 **Real-Time Updates (WebSocket)**

### Global WebSocket Connection

#### `WebSocket /ws`
Global event stream for dashboard/admin interfaces.

```javascript
// Connection
const ws = new WebSocket('ws://your-server:5000/ws');

// Message Types
{
  "type": "scene_activated",
  "data": {
    "sceneId": 1,
    "sceneName": "Living Room Display",
    "timestamp": "2025-08-21T15:45:00"
  },
  "sequenceId": 123
}

{
  "type": "display_connected", 
  "data": {
    "displayId": "display-001",
    "displayName": "Living Room TV"
  }
}

{
  "type": "channel_settings_updated",
  "data": {
    "channelId": "com.epaperframe.photoframe",
    "changes": ["poll_interval", "image_choice"]
  }
}
```

### Display-Specific WebSocket

#### `WebSocket /ws/display/{display_id}`
Display client-specific event stream.

```javascript
// Display client connection
const ws = new WebSocket('ws://your-server:5000/ws/display/display-001');

// Scene assignment updates
{
  "type": "scene_assigned",
  "data": {
    "sceneId": 1,
    "sceneName": "Family Photos",
    "channelId": "com.epaperframe.photoframe"
  }
}

// Poll interval updates
{
  "type": "poll_interval_updated",
  "data": {
    "newInterval": 300,
    "previousInterval": 600
  }
}
```

---

## 🛠 **Admin Operations**

### Channel Management

#### `POST /api/admin/reload-channels`
Reload channels from filesystem (useful when channel IDs change).

#### `GET /api/admin/channels/orphaned`
List database channels not found on filesystem.

#### `DELETE /api/admin/channels/{channel_id}`
Remove channel from database (filesystem untouched).

#### `POST /api/admin/channels/reset`
**🔄 Database Reset** - Clear all channels from database and rebuild from filesystem only.

```javascript
// Request (no body required)
fetch('/api/admin/channels/reset', { method: 'POST' })

// Response
{
  "success": true,
  "message": "Successfully reset channels database from filesystem",
  "summary": {
    "before": {
      "total_channels": 5,
      "channel_ids": ["old_weather", "photo_frame", "example_channel", "broken_channel", "weather_channel"]
    },
    "after": {
      "total_channels": 3,
      "channel_ids": ["com.epaperframe.photoframe", "example_channel", "weather_channel"]
    },
    "changes": {
      "removed_count": 3,
      "removed_ids": ["old_weather", "photo_frame", "broken_channel"],
      "added_count": 1,
      "added_ids": ["com.epaperframe.photoframe"],
      "kept_count": 2,
      "kept_ids": ["example_channel", "weather_channel"]
    }
  },
  "affected_scenes": [
    {
      "scene_id": 1,
      "scene_name": "Living Room Display",
      "channel_id": "photo_frame",
      "channel_name": "Photo Frame"
    }
  ],
  "warnings": [
    "1 scene(s) may need channel reassignment"
  ]
}
```

**⚠️ Important:** This is a destructive operation that:
- Removes ALL channels from database
- Rebuilds database from current filesystem state only
- May break scene assignments if channel IDs changed
- Cannot be undone

**Use Cases:**
- Clean up after major channel reorganization
- Resolve database/filesystem inconsistencies
- Start fresh after channel ID changes
- Remove all orphaned database entries at once

---

## 🎯 **React Integration Patterns**

### Plugin Loading System

```javascript
// 1. Fetch manifests
const manifests = await fetch('/api/channels/manifest').then(r => r.json());

// 2. Dynamic module loading
for (const manifest of manifests) {
  for (const ui of manifest.ui) {
    if (ui.renderMode === 'element') {
      // Load with integrity validation
      await import(/* webpackIgnore: true */ ui.moduleUrl);
    }
  }
}

// 3. React component usage
function ChannelConfigSlot({ channelId, hostProps }) {
  const uiElements = manifests
    .filter(m => m.id === channelId)
    .flatMap(m => m.ui)
    .filter(ui => ui.slots?.includes('dashboard.settings'));
    
  return (
    <>
      {uiElements.map((ui, i) => 
        React.createElement(ui.element, {
          key: i,
          'data-hostprops': JSON.stringify(hostProps)
        })
      )}
    </>
  );
}
```

### Display Client Polling Pattern

```javascript
class DisplayClient {
  constructor(displayId) {
    this.displayId = displayId;
    this.currentETag = null;
    this.pollInterval = 30000; // Default 30s
  }
  
  async pollForUpdates() {
    const headers = {};
    if (this.currentETag) {
      headers['If-None-Match'] = this.currentETag;
    }
    
    const response = await fetch(`/api/displays/${this.displayId}/current-image`, { headers });
    
    if (response.status === 304) {
      // No changes
      return { changed: false };
    }
    
    const data = await response.json();
    this.currentETag = response.headers.get('ETag');
    
    return { changed: true, ...data };
  }
  
  async connectWebSocket() {
    const ws = new WebSocket(`ws://your-server:5000/ws/display/${this.displayId}`);
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'poll_interval_updated') {
        this.pollInterval = message.data.newInterval * 1000;
        this.restartPolling();
      }
    };
  }
}
```

### Error Handling

```javascript
// Standard error response format
{
  "detail": "Error message",
  "status_code": 400
}

// Common status codes
// 200: Success
// 304: Not Modified (conditional requests)
// 400: Bad Request (validation errors)
// 404: Not Found
// 429: Rate Limited
// 500: Internal Server Error
```

---

## 📊 **Response Formats**

### Pagination
```javascript
{
  "items": [...],
  "pagination": {
    "total": 100,
    "limit": 20,
    "offset": 0,
    "hasMore": true
  }
}
```

### Success Responses
```javascript
{
  "success": true,
  "message": "Operation completed",
  "data": { ... }
}
```

### Change Detection
```javascript
{
  "lastModified": "2025-08-21T15:45:00",
  "contentHash": "a1b2c3d4e5f67890",
  "changeToken": "f7e8d9c6",
  "fileSize": 245760
}
```

---

## 🔒 **Headers & Caching**

### Important Headers
- `ETag`: For conditional requests
- `If-None-Match`: Send ETag to get 304 if unchanged
- `Cache-Control`: Caching directives
- `Content-Type`: `application/json` for API, `image/jpeg` for images

### Rate Limiting
- Most endpoints have built-in rate limiting
- Check response headers for rate limit status
- `/api/channels/manifest` has aggressive caching (10s TTL)

---

**💡 Need Help?** Check the full API documentation in `docs/API_DOCUMENTATION.md` for detailed examples and error scenarios.
