# Mimir Plugin Architecture Technical Specification

## Overview

This document outlines the new embedded plugin architecture for Mimir channels, replacing the current tightly-coupled system with a clean, extensible plugin framework that runs within the main API process.

## Architecture Goals

- **Decoupling**: Clean separation between main API and channel logic via embedded plugins
- **Extensibility**: Easy addition of new channel types without touching core code
- **Self-Containment**: Channels manage their own storage, UI, and business logic
- **Simplicity**: Minimal, standardized interface with embedded plugin loading
- **Performance**: Direct method calls instead of HTTP overhead

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
- **File System Scanning**: Main API scans configured channels directory for plugin.json files
- **Embedded Loading**: Plugins are loaded as Python modules into the main API process
- **Direct Integration**: Plugin routers are mounted on the main FastAPI application
- **No Separate Services**: No HTTP overhead or service management complexity

### Channel Structure
Each channel plugin:
- Provides a Python class implementing the plugin interface
- Includes plugin.json configuration file
- Manages own storage/database connections
- Exposes API endpoints via FastAPI router
- Provides manifest and health methods

### Channel Requirements
Every channel must provide:
1. **Plugin Class**: Python class with standardized methods (get_manifest, request_image, get_status)
2. **Plugin Configuration**: plugin.json with metadata and capabilities
3. **FastAPI Router**: Optional router for custom endpoints (get_router method)
4. **Entry Point**: Defined entry_point and class_name in plugin.json

### Embedded Plugin Pattern
Main API directly loads and integrates plugins:
- Plugin modules imported at startup
- Plugin instances created and stored in discovery service
- Plugin routers mounted at /api/channels/{channel_id}/
- Direct method calls for core functionality

## Implementation Details

### Main API Changes
- Replace current `channels.py` with new 4-endpoint structure
- Implement embedded plugin discovery service
- Add plugin module loading capabilities
- Remove all channel-specific business logic

### Plugin Interface
Plugins implement Python methods that main API calls directly:
```python
class ChannelPlugin:
    def get_manifest(self) -> Dict[str, Any]
    async def request_image(self, request_data: Dict[str, Any]) -> Dict[str, Any]
    def get_status(self) -> Dict[str, Any]
    def get_router(self) -> Optional[APIRouter]  # Optional custom endpoints
```

### Plugin Configuration Format
```json
{
  "id": "photo_frame",
  "name": "Photo Frame Channel", 
  "version": "1.0.0",
  "type": "embedded",
  "entry_point": "channel.py",
  "class_name": "PhotoFrameChannel",
  "description": "Photo gallery with randomization",
  "config": {
    "supports_upload": true,
    "image_formats": ["jpg", "jpeg", "png"]
  }
}
```

### Direct Method Integration
- Plugin discovery service loads modules using importlib
- Plugin instances created and cached in memory
- Main API calls plugin methods directly (no HTTP)
- Plugin routers mounted on main FastAPI app

## Migration Strategy

### Phase 1: Core API Replacement
1. Create embedded plugin discovery service
2. Replace channel endpoints with direct plugin integration
3. Implement plugin module loading and router mounting

### Phase 2: Photo Frame Conversion
1. Create PhotoFrameChannel as embedded plugin
2. Implement plugin.json configuration
3. Add gallery management and image generation methods

### Phase 3: Testing & Cleanup
1. End-to-end testing of embedded plugin architecture
2. Remove old channel code
3. Documentation updates

## Security Considerations

### Current Scope
- Private server deployment only
- Plugins run within main API process
- Direct Python method calls
- Shared main API security context

### Future Considerations
- Plugin sandboxing and isolation
- Resource usage monitoring
- Plugin permission system

## Benefits

### For Development
- Clean separation of concerns within single process
- Independent plugin development
- Easier testing and debugging
- Reduced main API complexity
- No service management overhead

### For Users
- Consistent interface across all channels
- Dynamic capability discovery
- Self-contained channel management
- Better performance (no HTTP overhead)

### For Operations
- Single service to deploy and manage
- No inter-service communication issues
- Simplified deployment
- Reduced infrastructure complexity

## Technical Notes

### Plugin Communication
- Direct Python method calls within same process
- JSON data structures for parameters
- FastAPI router integration for custom endpoints
- Shared application context and dependencies

### Asset Management
- Plugins can serve assets via mounted routers
- Static file serving through FastAPI
- Optional asset endpoints in plugin routers

### State Management
- Plugins manage own persistent state
- Access to shared application dependencies
- Database connections via dependency injection

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
