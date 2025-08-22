# Mimir Platform API Documentation

**Version:** 2.4  
**Last Updated:** August 21, 2025  
**Base URL:** `http://localhost:5000`  

---

## Table of Contents

1. [Overview](#overview)
2. [Core API Endpoints](#core-api-endpoints)
3. [Channel System v2.1](#channel-system-v21)
4. [Scene Management](#scene-management)
5. [Overlay System](#overlay-system)
6. [Display Management](#display-management)
7. [WebSocket Real-time Updates](#websocket-real-time-updates)
8. [Rate Limiting](#rate-limiting)
9. [Error Handling](#error-handling)
10. [Response Formats](#response-formats)
11. [Examples](#examples)

---

## Overview

The Mimir Platform provides a RESTful API for managing ambient display scenes, channels, overlays, and content. The API is built with FastAPI and follows REST conventions with JSON request/response bodies.

**Architecture v2.1** introduces a modern plugin system with filesystem-based channel discovery, Web Component UI support, and enhanced security features including Subresource Integrity (SRI) validation.

### Base URLs

- **Main API:** `http://localhost:5000/api`
- **Channel UI Assets:** `http://localhost:5000/api/channels/{id}/ui/`
- **Channel Static Assets:** `http://localhost:5000/api/channels/{id}/assets/`

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

## Rate Limiting

The API implements comprehensive rate limiting to prevent abuse and ensure fair usage across all clients.

### Global Rate Limiting

- **Limit:** 120 requests per minute per IP address
- **Window:** 60 seconds (sliding window)
- **Scope:** Per IP address
- **Applied to:** All API endpoints except static file serving

### Endpoint-Specific Rate Limiting

Some endpoints have additional rate limiting for optimal performance:

#### WebSocket Status Endpoint
- **Endpoint:** `GET /api/websocket/status`
- **Limit:** 50 requests per minute per IP
- **Purpose:** Prevent excessive polling of WebSocket status

#### Channel Manifest Endpoint
- **Endpoint:** `GET /api/channels/manifest`
- **Limit:** 100 requests per minute per IP
- **Cache Duration:** 10 seconds
- **Purpose:** Reduce load on manifest generation

### Rate Limit Response Headers

All API responses include rate limiting information:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1692451860
X-RateLimit-Window: 60
```

### Rate Limit Exceeded Response

When rate limits are exceeded, the API returns a 429 status code with detailed information:

```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "message": "Too many requests from 192.168.1.100",
    "limit": 120,
    "window_seconds": 60,
    "retry_after": 45,
    "current_requests": 121,
    "suggestion": "Please reduce request frequency or implement client-side caching",
    "endpoint": "/api/channels/example_channel/settings"
  }
}
```

### Rate Limit Bypass

Static file serving endpoints are not subject to rate limiting:
- `/api/channels/{id}/ui/`
- `/api/channels/{id}/assets/`
- Health check endpoints

### Best Practices

- **Implement exponential backoff** when receiving 429 responses
- **Cache responses locally** when appropriate
- **Monitor rate limit headers** to avoid hitting limits
- **Use WebSocket connections** for real-time updates instead of polling
- **Batch operations** when possible


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
      "description": "Shows current weather conditions with forecast",
      "relLogoImagePath": null,
      "version": "1.2.0",
      "settingsType": "simple",      
      "status": {
        "active": true,
        "lastUpdate": "2025-08-20T09:47:13.528309",
        "lastError": null,
        "usingFallback": false
      },
      "schemaVersion": "2.1",
      "permissions": ["read:weather"],
      "hasUI": true,
      "hasAssets": true,
      "channelDir": "channels/weather_channel"
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
  "update_interval_unit": {
    "type": "string",
    "enum": ["days", "hours", "minutes", "seconds"],
    "label": "Update Interval Unit",
    "default": "minutes",
    "value": "minutes"
  },
  "update_interval_value": {
    "type": "integer",
    "minimum": 1,
    "label": "Update Interval Value",
    "default": 30,
    "value": 15
  },
  "image_choice": {
    "type": "select",
    "enum": ["image1", "image2"],
    "label": "Image to Display",
    "default": "image1",
    "value": "image2"
  }
}
```

**Note:** The response includes both schema information (type, enum, label, default) and current values. The `value` field contains the actual current setting, while `default` shows the fallback value from the channel configuration.

#### POST `/api/channels/{channel_id}/settings`
Update channel settings with automatic type conversion and merging.

**Parameters:**
- `channel_id` (string): Channel identifier

**Request Body:**
```json
{
  "update_interval_value": "15",
  "image_choice": "image2"
}
```

**Response:**
```json
{
  "message": "Settings updated successfully"
}
```

**Features:**
- **Partial Updates**: Only specified settings are updated, others remain unchanged
- **Type Conversion**: String numbers are automatically converted to integers for numeric fields
- **Persistence**: Settings are merged with existing values and persist across server restarts
- **Real-time Broadcasting**: Changes trigger WebSocket events to all connected clients
- **Poll Interval Updates**: When `update_interval_*` settings change, all displays using scenes with this channel receive updated poll intervals via WebSocket
- **Display Synchronization**: Display clients automatically get notified of polling frequency changes

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
```

#### GET `/api/channels/manifest`
Get UI-aware manifests for React plugin loader (v2.1).

**Response:**
```json
[
  {
    "id": "weather_channel",
    "name": "Weather Display",
    "description": "Shows current weather conditions with forecast",
    "version": "1.2.0",
    "schemaVersion": "2.1",
    "permissions": ["read:weather"],
    "ui": [
      {
        "element": "x-weather-card",
        "moduleUrl": "/api/channels/weather_channel/ui/index.esm.js",
        "styleUrl": "/api/channels/weather_channel/ui/styles.css",
        "slots": ["dashboard.topRight"],
        "renderMode": "element",
        "propsSchema": {
          "$schema": "https://json-schema.org/draft/2020-12/schema",
          "type": "object",
          "properties": {
            "user": {"type": "object"},
            "theme": {"type": "string"}
          }
        },
        "integrity": {
          "module": "sha384-5KTNP4UMxHg0D31IeO3SJgz1h3r4XT4GcykOy3dYIfEqLQbO0L82tg81sP5hFge8",
          "style": "sha384-x4JTkDc0j6knV84b98wFp2jku9cOWMYOFeaQRUHwUu26AQhrRMY/HdoGdYjYO4hD"
        }
      }
    ],
    "assets": [
      {
        "name": "logo",
        "url": "/api/channels/weather_channel/assets/logo.svg"
      }
    ]
  }
]
```

#### POST `/api/channels/{channel_id}/test`
Test channel functionality (v2.1).

**Parameters:**
- `channel_id` (string): Channel identifier

**Response:**
```json
{
  "success": true,
  "channelId": "weather_channel",
  "status": {
    "active": true,
    "lastUpdate": "2025-08-20T09:48:56.926195",
    "lastError": null,
    "usingFallback": false,
    "version": "1.2.0"
  },
  "test_result": {
    "success": true,
    "message": "Weather channel is working correctly",
    "timestamp": "2025-08-20T09:48:48.076744"
  },
  "timestamp": "2025-08-20T09:48:48.076744"
}
```

#### GET `/api/channels/{channel_id}/health`
Get channel health status (v2.1).

**Parameters:**
- `channel_id` (string): Channel identifier

**Response:**
```json
{
  "channelId": "weather_channel",
  "name": "Weather Display",
  "version": "1.2.0",
  "status": {
    "active": true,
    "lastUpdate": "2025-08-20T09:48:56.926195",
    "lastError": null,
    "usingFallback": false,
    "version": "1.2.0"
  },
  "healthy": true,
  "lastCheck": "2025-08-20T09:48:56.931834"
}
```

#### GET `/api/channels/{channel_id}/token`
Get channel-scoped authentication token (v2.1).

**Parameters:**
- `channel_id` (string): Channel identifier

**Response:**
```json
{
  "token": "channel_weather_channel_1755708543",
  "channelId": "weather_channel",
  "permissions": ["read:weather"],
  "expiresIn": 3600,
  "tokenType": "Bearer"
}
```

#### Dynamic Channel APIs
Channels can define their own API endpoints that are automatically mounted under `/api/channels/{channel_id}/`. For example, the weather channel provides:

#### GET `/api/channels/weather_channel/forecast`
Get weather forecast data (channel-specific endpoint).

**Query Parameters:**
- `city` (string, optional): City name (default: "Seattle")

**Response:**
```json
{
  "city": "London",
  "current": {
    "tempC": 22,
    "tempF": 72,
    "condition": "Partly Cloudy",
    "humidity": 65,
    "windSpeed": 10
  },
  "forecast": [
    {
      "day": "Today",
      "high": 24,
      "low": 18,
      "condition": "Sunny"
    },
    {
      "day": "Tomorrow", 
      "high": 26,
      "low": 20,
      "condition": "Cloudy"
    }
  ],
  "lastUpdate": "2025-08-20T09:48:27.570275"
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

## Channel System v2.1

The v2.1 Channel System introduces a modern, filesystem-based plugin architecture with support for rich UI components and enhanced security.

### Key Features

- **🔍 Automatic Discovery** - Channels auto-discovered from `channels/` directory
- **🌐 Web Component UI** - Self-contained UI with ES Modules and Shadow DOM
- **🛡️ Security Hardening** - Subresource Integrity (SRI) validation and Content Security Policy
- **📦 Static Asset Serving** - Dedicated endpoints for UI and assets
- **🔌 Dynamic API Routes** - Channels can define their own API endpoints
- **⚡ Hot-Reload Ready** - Foundation for live channel updates

### Channel Directory Structure

Channels are self-contained directories under `channels/` with the following structure:

```
channels/
└── weather_channel/
    ├── config.json              # v2.1 manifest
    ├── channel.py               # Channel implementation
    ├── ui/                      # Optional: Web Component UI
    │   ├── index.esm.js         # Web Component entry (ESM)
    │   ├── page.esm.js          # Optional page component
    │   └── styles.css           # Scoped styles
    └── assets/                  # Static assets (images, fonts)
        └── logo.svg             # Channel logo
```

### Channel Discovery Process

1. **Scan** `channels/` directory for subdirectories
2. **Load** and validate `config.json` manifests
3. **Import** `channel.py` and instantiate channel class
4. **Mount** static file serving for UI and assets
5. **Register** channel-specific API routes
6. **Compute** SRI hashes for security validation
7. **Sync** channel data to database

### v2.1 Channel Manifest (config.json)

```json
{
  "schemaVersion": "2.1",
  "id": "weather_channel",
  "name": "Weather Display",
  "description": "Shows current weather conditions with forecast",
  "version": "1.2.0",
  "permissions": ["read:weather"],
  "settings_type": "simple",
  "settings": {
    "api_key": {
      "type": "string",
      "required": true,
      "secret": true,
      "label": "Weather API Key"
    },
    "location": {
      "type": "string",
      "required": true,
      "default": "Seattle",
      "label": "Default Location"
    }
  },
  "ui": [
    {
      "element": "x-weather-card",
      "moduleUrl": "/api/channels/weather_channel/ui/index.esm.js",
      "styleUrl": "/api/channels/weather_channel/ui/styles.css",
      "slots": ["dashboard.topRight"],
      "renderMode": "element",
      "propsSchema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
          "user": {"type": "object"},
          "theme": {"type": "string"}
        }
      }
    },
    {
      "route": "/weather",
      "element": "x-weather-page",
      "moduleUrl": "/api/channels/weather_channel/ui/page.esm.js",
      "nav": {"label": "Weather", "icon": "cloud"},
      "renderMode": "element"
    }
  ],
  "assets": [
    {
      "name": "logo",
      "url": "/api/channels/weather_channel/assets/logo.svg"
    }
  ]
}
```

### Channel Implementation Protocol

Channels implement a standardized Python interface:

```python
class WeatherChannel:
    def __init__(self, channel_dir: str):
        self.channel_dir = Path(channel_dir)
        
    @property
    def id(self) -> str:
        return "weather_channel"
        
    @property 
    def config(self) -> dict:
        # Load and return config.json
        
    async def render_image(self, resolution: tuple[int,int], orientation: str, settings: dict) -> str:
        # Generate display image, return path
        
    async def validate_settings(self, settings: dict) -> dict[str,str]:
        # Validate settings, return errors
        
    def get_status(self) -> dict:
        # Return channel health/status
        
    def get_router(self) -> Optional[APIRouter]:
        # Return FastAPI router for channel APIs (optional)
```

### UI Component Development

Channels can include Web Components for rich UI integration:

```javascript
// ui/index.esm.js - Weather Card Component
class WeatherCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  async connectedCallback() {
    const props = JSON.parse(this.getAttribute('data-hostprops') || '{}');
    const user = props.user || {};
    
    // Fetch data from channel API
    const response = await fetch(
      `/api/channels/weather_channel/forecast?city=${user.city || 'Seattle'}`,
      { credentials: 'include' }
    );
    const data = await response.json();
    
    // Render with Shadow DOM isolation
    this.render(data, props.theme);
  }
  
  render(weatherData, theme) {
    this.shadowRoot.innerHTML = `
      <style>/* Scoped styles */</style>
      <div class="weather-card">
        <h3>${weatherData.city}</h3>
        <div class="temp">${weatherData.current.tempC}°C</div>
        <div class="condition">${weatherData.current.condition}</div>
      </div>
    `;
  }
}

customElements.define('x-weather-card', WeatherCard);
```

### Security Features

#### Subresource Integrity (SRI)
- **Automatic hash computation** for all UI files (SHA-384)
- **Integrity validation** prevents tampering
- **Manifest includes hashes** for client-side verification

#### Content Security Policy
- **Restricted script execution** to validated sources
- **Style isolation** via Shadow DOM
- **Asset sandboxing** through dedicated mount points

#### Permission System
- **Channel-scoped permissions** declared in manifest
- **API token generation** with limited scope
- **Rate limiting** per channel (planned)

### Static File Serving

UI and assets are served via dedicated endpoints:

```
GET /api/channels/{channel_id}/ui/index.esm.js     # Web Component code
GET /api/channels/{channel_id}/ui/styles.css       # Scoped styles  
GET /api/channels/{channel_id}/assets/logo.svg     # Static assets
```

**Headers:**
- `Content-Type: application/javascript` for ES modules
- `Content-Type: text/css` for stylesheets
- SRI hashes included in manifest for validation

### React Integration

The v2.1 system provides everything needed for React plugin loading:

```javascript
// 1. Fetch channel manifests
const manifests = await fetch('/api/channels/manifest').then(r => r.json());

// 2. Load Web Components dynamically
for (const manifest of manifests) {
  for (const ui of manifest.ui) {
    if (ui.renderMode === 'element') {
      // Validate integrity hash (optional)
      await import(/* webpackIgnore: true */ ui.moduleUrl);
    }
  }
}

// 3. Use in React components
function PluginSlot({ name, hostProps }) {
  const uiElements = manifests
    .flatMap(m => m.ui)
    .filter(ui => ui.slots?.includes(name));
    
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

// 4. Use plugin slot in dashboard
<PluginSlot name="dashboard.topRight" hostProps={{ user, theme }} />
```

### Migration from v2.0

- **v2.0 channels continue working** unchanged
- **To add UI capabilities:**
  1. Add `ui/` directory with Web Components
  2. Update `config.json` with `ui` array
  3. Optionally add `get_router()` for custom APIs
- **Database automatically migrated** to v2.1 schema

---


## Display Management

The Mimir Platform supports both legacy single-display management and modern multi-display client architecture. The multi-display system allows multiple display devices to register, receive scene assignments, and fetch content independently.

### Legacy Display Management

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

#### POST `/api/display/clear`
Clear the display (remove current content).

**Response:**
```json
{
  "success": true
}
```

### Multi-Display Client System

The multi-display system enables centralized management of multiple display devices through a registration-based architecture.

#### Register Display Client

#### POST `/api/displays/register`
Register a new display client with the platform.

**Request Body:**
```json
{
  "name": "Conference Room Display",
  "description": "Main display for conference room presentations",
  "location": "Building A - Room 203",
  "capabilities": {
    "resolution": [1920, 1080],
    "supported_formats": ["jpg", "png", "gif"],
    "orientation": "landscape",
    "refresh_rate_hz": 60
  },
  "tags": ["conference", "presentation"],
  "client_version": "1.0.0"
}
```

**Response:**
```json
{
  "id": "f940535f-ad8e-459e-ba32-6e91380f2d69",
  "name": "Conference Room Display",
  "description": "Main display for conference room presentations",
  "location": "Building A - Room 203",
  "is_online": false,
  "last_seen": null,
  "assigned_scene_id": null,
  "assigned_scene_name": null,
  "resolution": [1920, 1080],
  "orientation": "landscape",
  "refresh_rate_hz": 60,
  "tags": ["conference", "presentation"],
  "client_version": "1.0.0",
  "current_image_url": null
}
```

#### List Display Clients

#### GET `/api/displays`
List all registered display clients with optional filtering.

**Query Parameters:**
- `online_only` (boolean, optional): Only return online displays
- `location` (string, optional): Filter by location
- `tag` (string, optional): Filter by tag

**Response:**
```json
[
  {
    "id": "f940535f-ad8e-459e-ba32-6e91380f2d69",
    "name": "Conference Room Display",
    "description": "Main display for conference room presentations",
    "location": "Building A - Room 203",
    "is_online": false,
    "last_seen": "2025-08-20T11:35:10.152765",
    "assigned_scene_id": "test-scene",
    "assigned_scene_name": "Test Scene",
    "resolution": [1920, 1080],
    "orientation": "landscape",
    "refresh_rate_hz": 60,
    "tags": ["conference", "presentation"],
    "client_version": "1.0.0",
    "current_image_url": "/api/displays/f940535f-ad8e-459e-ba32-6e91380f2d69/current_image"
  }
]
```

#### Assign Scene to Display

#### POST `/api/displays/{display_id}/assign_scene`
Assign a scene to a specific display client.

**Parameters:**
- `display_id` (string): Display client identifier

**Request Body:**
```json
{
  "scene_id": "test-scene"
}
```

**Response:**
```json
{
  "message": "Scene assignment updated for display Conference Room Display",
  "assigned_scene": "Test Scene",
  "message_sent": false
}
```

#### Unassign Scene from Display

#### DELETE `/api/displays/{display_id}/assign_scene`
Remove scene assignment from a display client.

**Parameters:**
- `display_id` (string): Display client identifier

**Response:**
```json
{
  "message": "Scene unassigned from display Conference Room Display",
  "message_sent": false
}
```

#### Get Current Image Metadata

#### GET `/api/displays/{display_id}/current_image`
Get metadata about the current image assigned to a display client with change detection support.

**Parameters:**
- `display_id` (string): Display client identifier

**Headers (Optional):**
- `If-None-Match` (string): Change token from previous request for conditional fetching

**Response:**
```json
{
  "display_id": "f940535f-ad8e-459e-ba32-6e91380f2d69",
  "scene_id": "test-scene",
  "scene_name": "Test Scene",
  "image_url": "/api/displays/f940535f-ad8e-459e-ba32-6e91380f2d69/current_image_file",
  "image_path": "/generated/displays/display_f940535f-ad8e-459e-ba32-6e91380f2d69_test-scene_1755715061.jpg",
  "resolution": [1920, 1080],
  "generated_at": "2025-08-21T11:37:41.923305",
  "channels": ["example_channel", "weather_channel"],
  "cache_expires_in": 300,
  "last_modified": "2025-08-21T11:35:20.451000",
  "content_hash": "a1b2c3d4e5f67890abcdef1234567890",
  "change_token": "f7e8d9c6b5a4",
  "file_size": 245760,
  "file_exists": true
}
```

**Change Detection Fields:**
- `last_modified`: ISO timestamp when the image file was last modified
- `content_hash`: MD5 hash of the image file contents  
- `change_token`: Short hash that changes when image content changes
- `file_size`: Size of the image file in bytes
- `file_exists`: Boolean indicating if the image file exists

**Conditional Requests:**
- Returns `304 Not Modified` if `If-None-Match` header matches current `change_token`
- Sets `ETag` header with current change token for future conditional requests
- Includes `Cache-Control: private, must-revalidate` header

**Error Response (No Scene Assigned):**
```json
{
  "error": "No scene assigned to this display",
  "display_id": "f940535f-ad8e-459e-ba32-6e91380f2d69",
  "display_name": "Conference Room Display"
}
```

#### Download Current Image

#### GET `/api/displays/{display_id}/current_image_file`
Download the actual image file for the display client.

**Parameters:**
- `display_id` (string): Display client identifier

**Response:** Binary image data (JPEG/PNG)

**Headers:**
- `Content-Type: image/jpeg` or `image/png`
- `Content-Length: {file_size}`
- `Last-Modified: {timestamp}`

#### Get Display Status

#### GET `/api/displays/{display_id}/status`
Get comprehensive status information for a specific display client, including poll interval calculation.

**Parameters:**
- `display_id` (string): Display client identifier

**Response:**
```json
{
  "display_id": "f940535f-ad8e-459e-ba32-6e91380f2d69",
  "name": "Conference Room Display",
  "location": "Building A - Room 203",
  "is_online": true,
  "last_seen": "2025-08-21T16:11:27.234567",
  "last_image_fetch": "2025-08-21T16:10:15.123456",
  "assigned_scene_id": "example-scene",
  "assigned_scene_name": "Example Scene",
  "current_image_url": "/api/displays/f940535f-ad8e-459e-ba32-6e91380f2d69/current_image_file",
  "resolution": [1920, 1080],
  "orientation": "landscape",
  "capabilities": {
    "supported_formats": ["jpg", "png"],
    "refresh_rate_hz": 60
  },
  "poll_interval": 900,
  "next_update_estimated": "2025-08-21T16:26:27.234567",
  "settings": {
    "brightness": 80,
    "sleep_schedule": "22:00-06:00"
  }
}
```

**Poll Interval Calculation:**
- **With Scene Assignment**: Calculated from the assigned scene's channel settings (`update_interval_unit` and `update_interval_value`) stored in the database
- **Without Scene Assignment**: Returns default value of 60 seconds (1 minute)  
- **Dynamic Updates**: Poll interval automatically recalculates whenever channel settings change via `/api/channels/{id}/settings`
- **Real-time Sync**: Changes propagate immediately to display clients via WebSocket events
- **Database-driven**: Uses current settings stored in database, not config file defaults

**No Scene Assigned Response:**
```json
{
  "display_id": "f940535f-ad8e-459e-ba32-6e91380f2d69",
  "name": "Conference Room Display",
  "location": "Building A - Room 203",
  "is_online": true,
  "last_seen": "2025-08-21T16:11:27.234567",
  "assigned_scene_id": null,
  "assigned_scene_name": null,
  "current_image_url": null,
  "poll_interval": 300,
  "message": "No scene assigned to this display"
}
```

#### Update Display Client

#### PUT `/api/displays/{display_id}`
Update display client information and settings.

**Parameters:**
- `display_id` (string): Display client identifier

**Request Body:**
```json
{
  "name": "Updated Conference Room Display",
  "description": "Updated description",
  "location": "Building A - Room 203B",
  "tags": ["conference", "presentation", "updated"],
  "settings": {
    "brightness": 80,
    "sleep_schedule": "22:00-06:00"
  }
}
```

**Response:**
```json
{
  "message": "Display client updated successfully",
  "display_id": "f940535f-ad8e-459e-ba32-6e91380f2d69"
}
```

#### Delete Display Client

#### DELETE `/api/displays/{display_id}`
Remove a display client from the system.

**Parameters:**
- `display_id` (string): Display client identifier

**Response:**
```json
{
  "message": "Display client Conference Room Display deleted successfully"
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

#### Display Client Events

**`display_client_registered`**
Broadcast when a new display client registers with the system.
```json
{
  "event": "display_client_registered",
  "data": {
    "displayId": "f940535f-ad8e-459e-ba32-6e91380f2d69",
    "name": "Conference Room Display",
    "location": "Building A - Room 203",
    "capabilities": {
      "resolution": [1920, 1080],
      "supported_formats": ["jpg", "png"],
      "orientation": "landscape",
      "refresh_rate_hz": 60
    },
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-20T11:30:00.000Z"
    }
  },
  "timestamp": "2025-08-20T11:30:00.000Z",
  "sequenceId": 12350
}
```

**`display_scene_assigned`**
Broadcast when a scene is assigned to a display client.
```json
{
  "event": "display_scene_assigned",
  "data": {
    "displayId": "f940535f-ad8e-459e-ba32-6e91380f2d69",
    "displayName": "Conference Room Display",
    "sceneId": "test-scene",
    "sceneName": "Test Scene",
    "previousSceneId": null,
    "assignedChannels": ["example_channel", "weather_channel"],
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-20T11:30:00.000Z"
    }
  },
  "timestamp": "2025-08-20T11:30:00.000Z",
  "sequenceId": 12351
}
```

**`display_scene_unassigned`**
Broadcast when a scene assignment is removed from a display client.
```json
{
  "event": "display_scene_unassigned",
  "data": {
    "displayId": "f940535f-ad8e-459e-ba32-6e91380f2d69",
    "displayName": "Conference Room Display",
    "previousSceneId": "test-scene",
    "previousSceneName": "Test Scene",
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-20T11:30:00.000Z"
    }
  },
  "timestamp": "2025-08-20T11:30:00.000Z",
  "sequenceId": 12352
}
```

**`display_connection_established`**
Sent to specific display client when WebSocket connection is established.
```json
{
  "event": "display_connection_established",
  "data": {
    "displayId": "f940535f-ad8e-459e-ba32-6e91380f2d69",
    "displayName": "Conference Room Display",
    "assignedScene": {
      "id": "test-scene",
      "name": "Test Scene",
      "channels": ["example_channel", "weather_channel"]
    }
  },
  "timestamp": "2025-08-20T11:30:00.000Z"
}
```

**`display_image_updated`**
Broadcast when a new image is generated for a display client.
```json
{
  "event": "display_image_updated",
  "data": {
    "displayId": "f940535f-ad8e-459e-ba32-6e91380f2d69",
    "displayName": "Conference Room Display",
    "sceneId": "test-scene",
    "sceneName": "Test Scene",
    "imageUrl": "/api/displays/f940535f-ad8e-459e-ba32-6e91380f2d69/current_image_file",
    "resolution": [1920, 1080],
    "generatedAt": "2025-08-20T11:37:41.923305",
    "channels": ["example_channel", "weather_channel"],
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-20T11:30:00.000Z"
    }
  },
  "timestamp": "2025-08-20T11:30:00.000Z",
  "sequenceId": 12353
}
```

### Display-Specific WebSocket Connections

#### WS `/ws/display/{display_id}`
Establish a WebSocket connection for a specific display client to receive targeted events.

**Connection URL:** `ws://localhost:5000/ws/display/{display_id}`

**Purpose:** Display clients can connect to receive events specific to their display, such as scene assignments and image updates.

**Connection Example (JavaScript):**
```javascript
const displayId = 'f940535f-ad8e-459e-ba32-6e91380f2d69';
const ws = new WebSocket(`ws://localhost:5000/ws/display/${displayId}`);

ws.onopen = function(event) {
    console.log(`Display ${displayId} WebSocket connected`);
};

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    
    switch(message.event) {
        case 'display_connection_established':
            console.log('Display connection established:', message.data);
            if (message.data.assignedScene) {
                fetchAndDisplayImage();
            }
            break;
        case 'scene_assigned':
            console.log('New scene assigned:', message.data.sceneName);
            fetchAndDisplayImage();
            break;
        case 'scene_unassigned':
            console.log('Scene unassigned');
            showDefaultContent();
            break;
        case 'image_updated':
            console.log('New image available');
            fetchAndDisplayImage();
            break;
    }
};

function fetchAndDisplayImage() {
    fetch(`/api/displays/${displayId}/current_image`)
        .then(response => response.json())
        .then(metadata => {
            if (metadata.image_url) {
                displayImage(metadata.image_url);
            }
        });
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
  "id": "weather_channel",
  "name": "Weather Display",
  "description": "Shows current weather conditions with forecast",
  "relLogoImagePath": null,
  "version": "1.2.0",
  "settingsType": "simple",
  "status": {
    "active": true,
    "lastUpdate": "2025-08-20T09:47:13.528309",
    "lastError": null,
    "usingFallback": false
  },
  "schemaVersion": "2.1",
  "permissions": ["read:weather"],
  "hasUI": true,
  "hasAssets": true,
  "channelDir": "channels/weather_channel"
}
```

---

## Photo Frame Channel API

The Photo Frame Channel (`com.epaperframe.photoframe`) provides digital photo frame functionality with intelligent image management, slideshow capabilities, and a comprehensive web-based management interface.

### Channel-Specific Endpoints

All Photo Frame Channel endpoints are prefixed with `/api/channels/com.epaperframe.photoframe/`

#### Image Management

##### GET `/images`
List all uploaded images with metadata including crop settings and display statistics.

**Response:**
```json
[
  {
    "id": 123,
    "filename": "image_abc123.jpg",
    "original_name": "sunset.jpg",
    "title": "Beautiful Sunset",
    "description": "Taken at the beach",
    "width": 1920,
    "height": 1080,
    "enabled": true,
    "times_shown": 5,
    "last_shown_at": "2025-08-21T09:15:00Z",
    "created_at": "2025-08-20T15:30:00Z",
    "crop_x": 0,
    "crop_y": 0,
    "crop_width": 100,
    "crop_height": 100,
    "preserve_aspect_ratio": false
  }
]
```

##### POST `/upload`
Upload new images to the photo frame collection with automatic processing.

**Request:** `multipart/form-data` with `files` field containing image files

**Response:**
```json
{
  "results": [
    {
      "filename": "sunset.jpg",
      "success": true,
      "image_id": 124
    },
    {
      "filename": "invalid.txt",
      "success": false,
      "error": "Unsupported file type"
    }
  ]
}
```

##### PUT `/images/{image_id}`
Update image metadata and intelligent crop settings for optimal display.

**Request Body** (form data):
- `title`: string - Image title for organization
- `description`: string - Image description  
- `crop_x`: float - Crop X position (0-100%)
- `crop_y`: float - Crop Y position (0-100%)
- `crop_width`: float - Crop width (0-100%)
- `crop_height`: float - Crop height (0-100%)
- `preserve_aspect_ratio`: boolean - Maintain original aspect ratio

**Response:**
```json
{
  "success": true
}
```

##### POST `/images/{image_id}/toggle`
Enable or disable an image in the slideshow rotation.

**Response:**
```json
{
  "success": true,
  "enabled": false
}
```

##### DELETE `/images/{image_id}`
Permanently remove an image from the collection.

**Response:**
```json
{
  "success": true
}
```

#### Settings Management

##### GET `/settings`
Get current photo frame configuration with slideshow and display preferences.

**Response:**
```json
{
  "slideshow_enabled": true,
  "order_mode": "added",
  "crop_mode": "smart_crop"
}
```

##### PUT `/settings`
Update photo frame configuration with automatic validation.

**Request Body:**
```json
{
  "slideshow_enabled": true,
  "order_mode": "random",
  "crop_mode": "letterbox"
}
```

**Available Settings:**
- `slideshow_enabled` (boolean): Enable automatic image rotation
- `order_mode` (string): Image order - "added", "random", or "custom"  
- `crop_mode` (string): Display mode - "smart_crop", "letterbox", or "stretch"

**Response:**
```json
{
  "success": true
}
```

#### Hardware and Status

##### GET `/hardware`
Get display hardware information and capabilities.

**Response:**
```json
{
  "display": "Inky",
  "resolution": [800, 600],
  "orientation": "landscape"
}
```

### Photo Frame Web Components

The Photo Frame Channel includes two Web Components for rich UI integration:

#### Dashboard Card: `x-photo-frame-card`
Compact display widget showing current image and basic statistics.

**Slots:** `dashboard.gallery`, `dashboard.sidebar`
**Element:** `<x-photo-frame-card>`
**Props:** Passed via `data-hostprops` attribute
- `user`: User context object
- `settings`: Current photo frame settings
- `stats`: Statistics including image count and last update

**Features:**
- Live image preview with automatic refresh
- Statistics display (total images, enabled images)
- Manual refresh button for testing
- Responsive design with error handling

#### Management Interface: `x-photo-frame-manager`
Full-featured management interface for photo frame administration.

**Route:** `/photo-frame`
**Element:** `<x-photo-frame-manager>`
**Navigation:** Appears in main navigation as "Photo Frame"

**Features:**
- **Drag & Drop Upload:** Multi-file image upload with progress
- **Image Grid:** Visual gallery with thumbnails and metadata
- **Smart Settings Panel:** Live configuration with instant preview
- **Individual Image Controls:** Enable/disable and delete actions
- **Responsive Layout:** Adapts to different screen sizes
- **Real-time Updates:** Automatic refresh of data and UI

### Integration Examples

#### React Dashboard Integration
```jsx
import { useState, useEffect } from 'react';

function PhotoFrameDashboard() {
  const [stats, setStats] = useState({});
  
  useEffect(() => {
    // Load photo frame status
    fetch('/api/channels/com.epaperframe.photoframe/status')
      .then(res => res.json())
      .then(setStats);
  }, []);

  return (
    <div className="dashboard-grid">
      <x-photo-frame-card 
        data-hostprops={JSON.stringify({
          user: { name: 'Current User' },
          settings: { slideshow_enabled: true },
          stats: stats
        })}
      />
    </div>
  );
}
```

#### Display Client Implementation
```javascript
// Photo Frame display client polling
class PhotoFrameDisplay {
  constructor(displayId) {
    this.displayId = displayId;
    this.pollInterval = 15 * 60 * 1000; // 15 minutes default
  }
  
  async checkForUpdates() {
    try {
      const response = await fetch(
        `/api/displays/${this.displayId}/current_image`,
        {
          headers: {
            'If-None-Match': this.lastChangeToken
          }
        }
      );
      
      if (response.status === 304) {
        console.log('No image changes');
        return;
      }
      
      const metadata = await response.json();
      this.lastChangeToken = metadata.change_token;
      
      // Download and display new image
      if (metadata.image_url) {
        await this.displayImage(metadata.image_url);
      }
      
    } catch (error) {
      console.error('Update check failed:', error);
    }
  }
  
  async displayImage(imageUrl) {
    const response = await fetch(imageUrl);
    const blob = await response.blob();
    const imageElement = document.getElementById('display-image');
    imageElement.src = URL.createObjectURL(blob);
  }
  
  start() {
    // Initial check
    this.checkForUpdates();
    
    // Set up polling
    setInterval(() => {
      this.checkForUpdates();
    }, this.pollInterval);
  }
}
```

### Error Handling

Photo Frame Channel API uses standard HTTP status codes with descriptive error messages:

**Validation Errors (400):**
```json
{
  "success": false,
  "errors": {
    "order_mode": "Must be one of: added, random, custom",
    "crop_mode": "Must be one of: smart_crop, letterbox, stretch"
  }
}
```

**Not Found Errors (404):**
```json
{
  "success": false,
  "error": "Image not found",
  "details": "No image with ID 999 exists"
}
```

**File Upload Errors:**
```json
{
  "results": [
    {
      "filename": "large_image.jpg",
      "success": false,
      "error": "File size exceeds 10MB limit"
    }
  ]
}
```

---

## Examples

### v2.1 Channel Development Workflow

1. **Check discovered channels:**
```bash
curl -X GET "http://localhost:5000/api/channels"
```

2. **Get UI manifests for React integration:**
```bash
curl -X GET "http://localhost:5000/api/channels/manifest"
```

3. **Test channel functionality:**
```bash
curl -X POST "http://localhost:5000/api/channels/weather_channel/test"
```

4. **Check channel health:**
```bash
curl -X GET "http://localhost:5000/api/channels/weather_channel/health"
```

5. **Access channel-specific APIs:**
```bash
curl -X GET "http://localhost:5000/api/channels/weather_channel/forecast?city=London"
```

6. **Access channel UI assets:**
```bash
# Web Component code
curl -X GET "http://localhost:5000/api/channels/weather_channel/ui/index.esm.js"

# Styles
curl -X GET "http://localhost:5000/api/channels/weather_channel/ui/styles.css"

# Static assets
curl -X GET "http://localhost:5000/api/channels/weather_channel/assets/logo.svg"
```

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


### Multi-Display Client Workflow Examples

#### Complete Display Client Setup

1. **Register a new display client:**
```bash
curl -X POST http://localhost:5000/api/displays/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lobby Display",
    "description": "Main entrance display",
    "location": "Building A - Main Entrance",
    "capabilities": {
      "resolution": [1920, 1080],
      "supported_formats": ["jpg", "png"],
      "orientation": "landscape",
      "refresh_rate_hz": 60
    },
    "tags": ["lobby", "entrance"],
    "client_version": "1.0.0"
  }'
```

2. **List all registered displays:**
```bash
curl -X GET "http://localhost:5000/api/displays"
```

3. **Create a scene for the display:**
```bash
curl -X POST http://localhost:5000/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lobby Information",
    "description": "Information display for lobby visitors",
    "channels": ["weather_channel", "example_channel"],
    "layout": {
      "grid": {"rows": 2, "cols": 1},
      "regions": [
        {"id": "top", "channel": "weather_channel", "position": [0, 0, 1, 1]},
        {"id": "bottom", "channel": "example_channel", "position": [0, 1, 1, 1]}
      ]
    }
  }'
```

4. **Assign scene to display:**
```bash
curl -X POST http://localhost:5000/api/displays/{display_id}/assign_scene \
  -H "Content-Type: application/json" \
  -d '{"scene_id": "lobby-information"}'
```

5. **Fetch current image metadata:**
```bash
curl -X GET "http://localhost:5000/api/displays/{display_id}/current_image"
```

6. **Download current image:**
```bash
curl -X GET "http://localhost:5000/api/displays/{display_id}/current_image_file" \
  --output current_display_image.jpg
```

#### Display Client Management

1. **Filter displays by location:**
```bash
curl -X GET "http://localhost:5000/api/displays?location=Building%20A"
```

2. **Show only online displays:**
```bash
curl -X GET "http://localhost:5000/api/displays?online_only=true"
```

3. **Filter by tag:**
```bash
curl -X GET "http://localhost:5000/api/displays?tag=conference"
```

4. **Update display information:**
```bash
curl -X PUT http://localhost:5000/api/displays/{display_id} \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Lobby Display",
    "settings": {
      "brightness": 75,
      "sleep_schedule": "22:00-06:00"
    }
  }'
```

5. **Unassign scene from display:**
```bash
curl -X DELETE "http://localhost:5000/api/displays/{display_id}/assign_scene"
```

6. **Remove display client:**
```bash
curl -X DELETE "http://localhost:5000/api/displays/{display_id}"
```

#### Display Client Polling Pattern

**Simple polling implementation:**
```bash
#!/bin/bash
DISPLAY_ID="f940535f-ad8e-459e-ba32-6e91380f2d69"
POLL_INTERVAL=30

while true; do
  echo "Checking for updates..."
  
  # Get current image metadata
  RESPONSE=$(curl -s "http://localhost:5000/api/displays/${DISPLAY_ID}/current_image")
  
  if echo "$RESPONSE" | grep -q "image_url"; then
    # Extract image URL and download
    IMAGE_URL=$(echo "$RESPONSE" | jq -r '.image_url')
    curl -s "http://localhost:5000${IMAGE_URL}" --output current_image.jpg
    echo "Image updated: current_image.jpg"
  else
    echo "No scene assigned or image available"
  fi
  
  sleep $POLL_INTERVAL
done
```

#### Optimized Polling with Change Detection

**Efficient polling using conditional requests:**
```bash
#!/bin/bash
DISPLAY_ID="f940535f-ad8e-459e-ba32-6e91380f2d69"
POLL_INTERVAL=30
CHANGE_TOKEN=""

while true; do
  echo "Checking for updates..."
  
  # Build conditional request headers
  HEADERS=""
  if [ ! -z "$CHANGE_TOKEN" ]; then
    HEADERS="-H \"If-None-Match: $CHANGE_TOKEN\""
  fi
  
  # Check for image changes
  RESPONSE=$(eval "curl -s -w '%{http_code}' $HEADERS \"http://localhost:5000/api/displays/${DISPLAY_ID}/current_image\"")
  HTTP_CODE=$(echo "$RESPONSE" | tail -c 4)
  BODY=$(echo "$RESPONSE" | head -c -4)
  
  if [ "$HTTP_CODE" = "304" ]; then
    echo "Image unchanged, skipping download"
  elif [ "$HTTP_CODE" = "200" ]; then
    echo "Image changed, downloading..."
    
    # Extract new change token and image URL
    NEW_TOKEN=$(echo "$BODY" | jq -r '.change_token')
    IMAGE_URL=$(echo "$BODY" | jq -r '.image_url')
    
    # Download new image
    curl -s "http://localhost:5000${IMAGE_URL}" --output current_image.jpg
    echo "Image updated: current_image.jpg (token: $NEW_TOKEN)"
    
    CHANGE_TOKEN="$NEW_TOKEN"
  else
    echo "Error or no scene assigned"
  fi
  
  sleep $POLL_INTERVAL
done
```

**Python example with change detection:**
```python
import requests
import time

class DisplayClient:
    def __init__(self, display_id, base_url):
        self.display_id = display_id
        self.base_url = base_url
        self.last_change_token = None
        
    def check_for_updates(self):
        headers = {}
        if self.last_change_token:
            headers['If-None-Match'] = self.last_change_token
            
        response = requests.get(
            f"{self.base_url}/api/displays/{self.display_id}/current_image",
            headers=headers
        )
        
        if response.status_code == 304:
            print("Image unchanged, skipping download")
            return False
            
        if response.status_code == 200:
            metadata = response.json()
            print(f"Image changed: {metadata['change_token']}")
            
            # Download new image
            self.download_image(metadata['image_url'])
            self.last_change_token = metadata['change_token']
            return True
            
    def download_image(self, image_url):
        response = requests.get(f"{self.base_url}{image_url}")
        with open("current_display.jpg", "wb") as f:
            f.write(response.content)
            
    def run_polling_loop(self, interval=30):
        while True:
            try:
                self.check_for_updates()
            except Exception as e:
                print(f"Error checking for updates: {e}")
            time.sleep(interval)

# Usage
client = DisplayClient("your-display-id", "http://localhost:5000")
client.run_polling_loop()
```

### Display Management

1. **Check legacy display status:**
```bash
curl -X GET http://localhost:5000/api/display/status
```

2. **Display scene immediately (legacy):**
```bash
curl -X POST http://localhost:5000/api/scenes/morning-gallery/display
```

3. **Clear display (legacy):**
```bash
curl -X POST http://localhost:5000/api/display/clear
```

---

## Rate Limiting

The API implements rate limiting to prevent abuse and ensure fair usage across all clients.

### Rate Limit Configuration

- **Limit:** 120 requests per minute per IP address
- **Window:** 60 seconds (sliding window)
- **Scope:** Per IP address
- **Method:** All API endpoints except static file serving

### Rate Limit Headers

All API responses include rate limiting information in headers:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1692451860
```

### Rate Limit Exceeded Response

When rate limits are exceeded, the API returns a 429 status code:

```json
{
  "detail": "Rate limit exceeded. Maximum 120 requests per minute allowed."
}
```

### Best Practices for Display Clients

- **Implement exponential backoff** when receiving 429 responses
- **Cache images locally** to reduce API calls
- **Use appropriate polling intervals** (recommended: 30-60 seconds for image checks)
- **Monitor rate limit headers** to avoid hitting limits
- **Batch operations** when possible

### Rate Limit Bypass

Static file serving endpoints (UI assets, images) are not subject to rate limiting:
- `/api/channels/{id}/ui/`
- `/api/channels/{id}/assets/`
- `/api/displays/{id}/current_image_file`

---


## Changelog

### v2.4.1 (August 21, 2025)
- **🔍 Image Change Detection** - Complete change detection system for display clients
- **⚡ Performance Optimization** - Conditional requests to reduce bandwidth usage
- **📱 Enhanced Display Clients** - Better polling patterns with change detection
- **🖼️ Smart Image Management** - File metadata tracking and content hashing
- **🆕 New Features:**
  - Added `last_modified`, `content_hash`, `change_token`, `file_size`, and `file_exists` fields to current image endpoint
  - Support for `If-None-Match` conditional headers 
  - Returns `304 Not Modified` when images haven't changed
  - Enhanced example channel with dynamic asset discovery
  - Automatic `current.jpg` creation when settings change
  - New example channel endpoints: `/assets` and `/refresh_assets`
- **📈 Performance Benefits:**
  - Display clients can skip unnecessary downloads
  - Reduced server load with 304 responses
  - Lower bandwidth usage for unchanged content
  - Better battery life for mobile/embedded displays

### v2.4 (August 21, 2025)
- **🔧 Enhanced Settings Management** - Complete overhaul of channel settings persistence
- **🔄 Dynamic Settings Merging** - Partial updates with automatic type conversion
- **📊 Poll Interval Calculation** - Dynamic poll intervals based on channel settings
- **🛡️ Enhanced Rate Limiting** - Comprehensive rate limiting with detailed error responses
- **📈 Settings Broadcasting** - Real-time WebSocket events for settings changes
- **🔍 Improved Error Handling** - Better error messages and recovery suggestions
- **📝 Updated Documentation** - Comprehensive documentation updates reflecting current implementation
- **🆕 New Features:**
  - Settings values now persist across server restarts
  - String to integer conversion for numeric settings
  - Display status includes calculated poll intervals
  - Enhanced rate limiting with endpoint-specific limits
  - Real-time settings change broadcasting via WebSocket
- **🐛 Bug Fixes:**
  - Fixed SQLAlchemy JSON column update detection
  - Resolved settings persistence issues
  - Corrected poll interval calculation logic
  - Improved display status endpoint accuracy

### v2.3 (August 20, 2025)
- **🖥️ Multi-Display Client System** - Complete multi-display architecture implementation
- **📋 Display Client Registration** - Registration system with capabilities tracking
- **🎯 Scene Assignment** - Assign specific scenes to individual displays  
- **🖼️ Display Image Generation** - On-demand image generation per display
- **📡 Display-Specific WebSockets** - Targeted WebSocket connections at `/ws/display/{id}`
- **🛡️ Rate Limiting** - 120 requests/minute protection against abuse
- **📊 New v2.3 Endpoints:**
  - `POST /api/displays/register` - Register display clients
  - `GET /api/displays` - List all display clients with filtering
  - `POST /api/displays/{id}/assign_scene` - Assign scenes to displays
  - `DELETE /api/displays/{id}/assign_scene` - Unassign scenes from displays
  - `GET /api/displays/{id}/current_image` - Get image metadata for display
  - `GET /api/displays/{id}/current_image_file` - Download image for display
  - `GET /api/displays/{id}/status` - Get comprehensive display status
  - `PUT /api/displays/{id}` - Update display client information
  - `DELETE /api/displays/{id}` - Remove display client
- **🔄 Enhanced WebSocket Events:**
  - `display_client_registered` - New display registration notifications
  - `display_scene_assigned` - Scene assignment notifications
  - `display_scene_unassigned` - Scene unassignment notifications
  - `display_connection_established` - Display-specific connection events
  - `display_image_updated` - Image generation notifications
- **🏗️ Production Ready Features:**
  - Rate limiting with configurable thresholds
  - Display client filtering and management
  - Image caching and generation pipeline
  - Comprehensive error handling
  - WebSocket connection management for displays

### v2.1 (August 2025)
- **🚀 Channel Architecture v2.1** - Complete overhaul of plugin system
- **🔍 Filesystem-based Discovery** - Automatic channel discovery from `channels/` directory
- **🌐 Web Component Support** - Self-contained UI with ES Modules and Shadow DOM
- **🛡️ Enhanced Security** - Subresource Integrity (SRI) validation for UI assets
- **📦 Static Asset Serving** - Dedicated endpoints for UI and assets at `/api/channels/{id}/ui/` and `/api/channels/{id}/assets/`
- **🔌 Dynamic API Routes** - Channels can define custom API endpoints
- **📊 New v2.1 Endpoints:**
  - `GET /api/channels/manifest` - UI manifests for React plugin loader
  - `POST /api/channels/{id}/test` - Channel functionality testing
  - `GET /api/channels/{id}/health` - Channel health monitoring
  - `GET /api/channels/{id}/token` - Channel-scoped authentication tokens
- **🎯 React Integration Ready** - Complete plugin loading system for React frontends
- **📈 Enhanced Channel Responses** - Added `schemaVersion`, `permissions`, `hasUI`, `hasAssets`, `channelDir`
- **⚡ Performance Improvements** - Efficient static file serving and database connection pooling
- **🔄 Backwards Compatibility** - v2.0 channels continue to work unchanged

### v1.1 (August 2025)
- Enhanced WebSocket real-time updates with full state broadcast
- Sequence ID tracking for message ordering
- Heartbeat/ping-pong connection health monitoring
- Enhanced event context with previous state information
- Error broadcasting with recovery suggestions
- Channel status updates in real-time
- Connection status endpoint at `/api/websocket/status`

### v1.0 (August 2025)
- Initial API implementation with FastAPI
- SQLite database integration with SQLAlchemy
- Core scene management endpoints
- Channel management with configuration schemas
- Overlay system endpoints
- Display management endpoints
- WebSocket real-time updates for live scene synchronization
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
