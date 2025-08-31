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
Returns dynamically generated manifest with current channel capabilities and web UI integration:
```json
{
  "id": "com.epaperframe.photoframe",
  "name": "Photo Frame Channel", 
  "version": "1.0.0",
  "description": "Gallery-based photo slideshow with intelligent image management",
  "capabilities": {
    "supports_upload": true,
    "supports_gallery": true,
    "supports_randomization": true,
    "image_formats": ["jpg", "jpeg", "png", "gif"],
    "max_file_size": "10MB"
  },
  "ui": {
    "entry_point": "/api/channels/com.epaperframe.photoframe/ui/index.html",
    "components": {
      "manager": "/api/channels/com.epaperframe.photoframe/ui/manage.esm.js",
      "gallery_card": "/api/channels/com.epaperframe.photoframe/ui/components/gallery-card.js",
      "image_card": "/api/channels/com.epaperframe.photoframe/ui/components/image-card.js"
    },
    "styles": "/api/channels/com.epaperframe.photoframe/ui/styles.css",
    "icon": "🖼️",
    "title": "Photo Frame Manager"
  },
  "galleries": [
    {
      "id": "fresh_gallery",
      "name": "Fresh Gallery", 
      "image_count": 1
    }
  ],
  "status": {
    "active": true,
    "healthy": true,
    "lastUpdate": "2025-08-28T20:22:57.098881",
    "lastError": null,
    "version": "1.0.0",
    "galleries": 9,
    "totalImages": 5
  }
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
  "id": "com.epaperframe.photoframe",
  "name": "Photo Frame Channel", 
  "description": "Gallery-based photo slideshow with intelligent image management",
  "version": "1.0.0",
  "type": "embedded",
  "entry_point": "channel.py",
  "class_name": "PhotoFrameChannel",
  "icon": "photo",
  "author": "Mimir Platform",
  "tags": ["photo", "gallery", "slideshow", "display"],
  "config": {
    "supports_upload": true,
    "supports_gallery": true,
    "image_formats": ["jpg", "jpeg", "png", "gif"],
    "max_file_size": "10MB"
  },
  "requirements": {
    "python": ">=3.8",
    "dependencies": ["fastapi", "pillow", "sqlalchemy"]
  }
}
```

### Direct Method Integration
- Plugin discovery service loads modules using importlib
- Plugin instances created and cached in memory
- Main API calls plugin methods directly (no HTTP)
- Plugin routers mounted on main FastAPI app

## Migration Strategy

### Phase 1: Core API Replacement ✅ COMPLETE
1. ✅ Created embedded plugin discovery service
2. ✅ Replaced channel endpoints with direct plugin integration
3. ✅ Implemented plugin module loading and router mounting

### Phase 2: Photo Frame Conversion ✅ COMPLETE
1. ✅ Created PhotoFrameChannel as embedded plugin
2. ✅ Implemented plugin.json configuration
3. ✅ Added gallery management and image generation methods

### Phase 3: Testing & Cleanup ✅ COMPLETE
1. ✅ End-to-end testing of embedded plugin architecture
2. ✅ Web UI integration and gallery management
3. ✅ Removed redundant code and optimized manifest structure
4. ✅ Documentation updates

### Phase 4: Production Deployment ✅ COMPLETE
1. ✅ Full system testing with existing data (9 galleries, 5 images)
2. ✅ Performance validation and optimization
3. ✅ Complete web UI functionality verification

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

## Implementation Status

### ✅ COMPLETED IMPLEMENTATION

**Date Completed**: August 28, 2025  
**Status**: Production Ready

### Key Achievements

1. **🏗️ Embedded Plugin Architecture**
   - Complete conversion from HTTP microservices to embedded Python modules
   - Plugin discovery service with file system scanning and dynamic loading
   - Direct method calls for optimal performance (no HTTP overhead)
   - FastAPI router integration for custom plugin endpoints

2. **📸 Photo Frame Plugin Implementation**
   - Full gallery management system with CRUD operations
   - Image upload, processing, and storage
   - Random image selection with configurable options
   - Gallery settings and content assignment
   - Snake_case to camelCase API compatibility layer

3. **🌐 Complete Web UI Integration**
   - React-style web components (gallery-card, image-card, manage.esm.js)
   - Full-featured gallery management interface
   - Drag-and-drop image reordering
   - Real-time gallery content updates
   - Settings management with modal dialogs

4. **📋 Enhanced Manifest System**
   - Dynamic manifest generation with UI component references
   - Clean status reporting (removed redundant data)
   - Complete capability discovery
   - Web UI entry points and component mapping

5. **🔧 Production Validation**
   - Tested with existing production data (9 galleries, 5 images)
   - Complete CRUD functionality through web interface
   - Performance optimization and error handling
   - Seamless migration from previous architecture

### Architecture Benefits Achieved

- **Performance**: Direct Python method calls eliminated HTTP overhead
- **Simplicity**: Single service deployment with embedded plugins
- **Maintainability**: Clean separation of concerns within unified codebase
- **Extensibility**: Plugin system ready for future channel additions
- **User Experience**: Complete web UI for gallery and image management

### Technical Implementation Details

- **Plugin Loading**: importlib-based module loading with dependency injection
- **API Structure**: 4-endpoint core API with mounted plugin routers
- **Data Format**: JSON with automatic snake_case/camelCase conversion
- **UI Integration**: Static file serving through mounted plugin assets
- **Error Handling**: Comprehensive error handling with graceful degradation

### Current System Capabilities

- **Gallery Management**: Create, read, update, delete galleries
- **Image Operations**: Upload, assign, reorder, delete images
- **Settings Management**: Gallery-specific and global configuration
- **Web Interface**: Complete management UI with modern components
- **API Access**: RESTful endpoints for all operations
- **Plugin Discovery**: Automatic detection and loading of new plugins
