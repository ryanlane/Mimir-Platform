# Mimir Plugin Architecture Technical Specification

## Overview

This document outlines the new plugin-based architecture for Mimir channels, replacing the current tightly-coupled system with a clean, extensible plugin framework.

## Architecture Goals

- **Decoupling**: Complete separation between main API and channel logic
- **Extensibility**: Easy addition of new channel types without touching core code
- **Self-Containment**: Channels manage their own storage, UI, and business logic
- **Simplicity**: Minimal, standardized interface between main API and channels

## Core API Endpoints

The main Mimir API will expose only 4 endpoints for all channel operations:

### 1. List Channels
```
GET /api/channels/
```
Returns basic information about all available channel plugins:
```json
{
  "channels": [
    {
      "id": "com.epaperframe.photoframe",
      "name": "Photo Frame",
      "description": "Gallery-based photo slideshow",
      "icon": "/api/channels/com.epaperframe.photoframe/assets/icon.png"
    }
  ]
}
```

### 2. Get Channel Manifest
```
GET /api/channels/{channel_id}/manifest
```
Returns dynamically generated manifest with current channel capabilities:
```json
{
  "id": "com.epaperframe.photoframe",
  "name": "Photo Frame",
  "description": "Gallery-based photo slideshow",
  "icon": "/api/channels/com.epaperframe.photoframe/assets/icon.png",
  "imageEndpoints": [
    {
      "id": "gallery_one",
      "name": "Gallery One",
      "description": "This is gallery one!",
      "source": "/api/channels/com.epaperframe.photoframe/galleries/gallery_one",
      "options": [
        {
          "name": "order_mode",
          "type": "string",
          "value": "added",
          "options_source": "/api/channels/com.epaperframe.photoframe/galleries/gallery_one/options/order_mode"
        },
        {
          "name": "crop_mode",
          "type": "string",
          "value": "smart_crop",
          "options_source": "/api/channels/com.epaperframe.photoframe/galleries/gallery_one/options/crop_mode"
        },
        {
          "name": "update_interval_unit",
          "type": "string",
          "value": "minutes",
          "options_source": "/api/channels/com.epaperframe.photoframe/galleries/gallery_one/options/update_interval_unit"
        },
        {
          "name": "update_interval_value",
          "type": "integer",
          "value": 30
        },
        {
          "name": "width",
          "type": "integer",
          "value": 800
        },
        {
          "name": "height",
          "type": "integer",
          "value": 480
        }
      ]
    }
  ],
  "uiComponent": "/api/channels/com.epaperframe.photoframe/ui/manage.esm.js",
  "staticAssets": "/api/channels/com.epaperframe.photoframe/assets"
}
```

### 3. Channel Health Check
```
GET /api/channels/{channel_id}/health
```
Returns channel health status (same as current implementation).

### 4. Request Image
```
POST /api/channels/{channel_id}/request_image
```
Request image generation with specific options:
```json
{
  "endpoint_id": "gallery_one",
  "options": {
    "order_mode": "random",
    "crop_mode": "smart_crop",
    "width": 800,
    "height": 480
  }
}
```

## Channel Plugin Architecture

### Channel Discovery
- **File System Scanning**: Main API scans configured channels directory
- **Auto-Discovery**: Channels are automatically detected and loaded
- **No Registration Required**: Just add to channels directory

### Channel Structure
Each channel plugin:
- Runs as independent HTTP service
- Manages own database/storage
- Provides own UI components
- Serves own static assets
- Implements standardized endpoints

### Channel Requirements
Every channel must provide:
1. **Manifest Endpoint**: Dynamic capability description
2. **Image Request Endpoint**: Image generation with options
3. **Health Endpoint**: Status reporting
4. **UI Component**: Web component for management interface
5. **Static Assets**: Icons, stylesheets, etc.

### HTTP Proxy Pattern
Main API acts as reverse proxy:
- Routes requests to appropriate channel services
- Handles authentication/security at main API level
- Channels focus purely on business logic

## Implementation Details

### Main API Changes
- Replace current `channels.py` with new 4-endpoint structure
- Implement channel discovery service
- Add HTTP proxying capabilities
- Remove all channel-specific business logic

### Channel Service Interface
Channels implement HTTP endpoints that main API proxies to:
```
GET /{channel_id}/manifest
POST /{channel_id}/request_image
GET /{channel_id}/health
GET /{channel_id}/ui/manage.esm.js
GET /{channel_id}/assets/*
```

### Dynamic Manifest Generation
- Manifests generated at request time
- Reflects current channel state (galleries, options, etc.)
- No static configuration files

### UI Integration
- Main web UI loads channel UI components via ES modules
- Components embedded directly into management interface
- Channels provide complete UI logic

## Migration Strategy

### Phase 1: Core API Replacement
1. Create new channel discovery service
2. Replace channel endpoints with proxy implementation
3. Maintain backward compatibility temporarily

### Phase 2: Photo Frame Conversion
1. Extract photo frame logic to standalone service
2. Implement manifest generation
3. Update UI component for new architecture

### Phase 3: Testing & Cleanup
1. End-to-end testing of new architecture
2. Remove old channel code
3. Documentation updates

## Security Considerations

### Current Scope
- Private server deployment only
- No authentication between main API and channels
- Simple HTTP communication

### Future Considerations
- Inter-service authentication
- Request validation
- Rate limiting

## Benefits

### For Development
- Clean separation of concerns
- Independent channel development
- Easier testing and debugging
- Reduced main API complexity

### For Users
- Consistent interface across all channels
- Dynamic capability discovery
- Self-contained channel management

### For Operations
- Independent channel scaling
- Isolated channel failures
- Simplified deployment

## Technical Notes

### Channel Communication
- HTTP-based communication between main API and channels
- JSON payload formats
- RESTful endpoint design

### Asset Management
- Channels serve own static assets
- Main API proxies asset requests
- No shared asset storage

### State Management
- Channels manage own persistent state
- No shared database dependencies
- Independent backup/restore capabilities

## Future Enhancements

### Potential Additions
- WebSocket support for real-time updates
- Plugin marketplace/registry
- Advanced authentication mechanisms
- Cross-channel communication
- Monitoring and metrics integration

### Extensibility Points
- Custom option types
- Advanced UI component features
- Webhook integrations
- Custom routing patterns
