# Mimir Plugin Architecture - Implementation TODO

## Project Status: PHASE 1 COMPLETE ✅

**Objective**: Replace current tightly-coupled channel system with clean embedded plugin architecture

**Key Deliverable**: 4-endpoint main API with embedded plugin loading (NOT microservices)

**Architecture Decision**: **EMBEDDED PLUGINS** - Plugins load as Python modules into main API process, not as separate HTTP services

---

## Phase 1: Core API Infrastructure 🔧 - COMPLETE ✅

### Main API Changes
- [x] **Replace channels.py**
  - [x] Remove all existing channel endpoints (subchannels, settings, images, etc.)
  - [x] Implement new 4-endpoint structure
  - [x] Update to work with embedded plugins (removed HTTP client/proxy)
  - [x] Handle direct method calls to plugin instances

- [x] **Plugin Discovery Service** 
  - [x] Create new plugin_discovery.py service
  - [x] File system scanning for plugin.json files
  - [x] Plugin module loading using importlib
  - [x] Plugin instance creation and caching
  - [x] FastAPI router mounting for custom endpoints
  - [x] Configuration loading

- [x] **Embedded Plugin Integration**
  - [x] Direct method calls to plugin instances
  - [x] Plugin router mounting on main FastAPI app
  - [x] Error handling for plugin operations
  - [x] Plugin lifecycle management

- [x] **API Endpoint Implementation**
  ```
  GET /api/channels/               -> List all discovered plugins ✅
  GET /api/channels/{id}/manifest  -> Call plugin.get_manifest() ✅
  GET /api/channels/{id}/health    -> Call plugin.get_status() ✅
  POST /api/channels/{id}/request_image -> Call plugin.request_image() ✅
  ```

### Infrastructure Updates
- [x] **Dependencies**
  - [x] Remove HTTP client dependencies (httpx not needed)
  - [x] Add importlib for module loading
  - [x] Update FastAPI routing for plugin integration

- [x] **Configuration**
  - [x] Channel directory configuration
  - [x] Plugin discovery settings
  - [x] Embedded plugin configuration support

---

## Phase 2: Photo Frame Plugin Implementation 📸 - COMPLETE ✅

### Embedded Plugin Creation
- [x] **Create PhotoFrameChannel Plugin**
  - [x] Implement PhotoFrameChannel class with plugin interface
  - [x] Add gallery discovery and management
  - [x] Implement request_image method for random image selection
  - [x] Create plugin.json configuration file
  - [x] Add gallery directory structure

- [x] **Plugin Interface Implementation**
  - [x] `get_manifest()` - Dynamic manifest generation with capabilities
  - [x] `request_image()` - Random image selection from gallery
  - [x] `get_status()` - Plugin health and statistics
  - [x] `get_router()` - Custom endpoints for gallery management

- [x] **Plugin Configuration**
  - [x] Updated plugin.json for embedded architecture
  - [x] Removed service_url and HTTP-related configuration
  - [x] Added embedded plugin metadata (entry_point, class_name)
  - [x] Defined plugin capabilities and endpoints

### Gallery Management Features
- [x] **Core Functionality**
  - [x] Gallery image discovery
  - [x] Random image selection
  - [x] Base64 image encoding for API responses
  - [x] Placeholder image generation when gallery empty
  - [x] Image format support (jpg, jpeg, png, gif)

- [x] **Plugin Endpoints** (via get_router())
  - [x] `GET /manifest` - Plugin capabilities
  - [x] `POST /request_image` - Random image generation
  - [x] `GET /gallery` - List gallery images
  - [x] `POST /upload` - Image upload functionality

---

## Phase 3: Integration & Testing 🔬 - READY FOR TESTING

### Plugin Integration
- [x] **Plugin Loading**
  - [x] Plugin discovery service loads PhotoFrameChannel module
  - [x] Plugin instance creation and router mounting
  - [x] Main API integration with embedded plugins
  - [x] Plugin endpoint routing configuration

- [ ] **End-to-End Testing**
  - [ ] Test plugin discovery (should show photo_frame)
  - [ ] Test manifest generation with gallery capabilities
  - [ ] Test image request flow (random image from gallery)
  - [ ] Test custom plugin endpoints (gallery, upload)
  - [ ] Test with sample images in gallery

### Data Setup
- [ ] **Test Data Preparation**
  - [ ] Add sample images to gallery directory
  - [ ] Test image discovery and random selection
  - [ ] Verify placeholder generation when no images
  - [ ] Test upload functionality

---

## Phase 4: Cleanup & Documentation 📚

### Code Cleanup
- [ ] **Remove Old Code**
  - [ ] Delete old channel-specific endpoints
  - [ ] Remove unused service dependencies
  - [ ] Clean up import statements
  - [ ] Update API documentation

- [ ] **Documentation Updates**
  - [ ] Update API documentation for new endpoints
  - [ ] Create channel development guide
  - [ ] Update deployment instructions
  - [ ] Document proxy configuration

---

## Testing Checklist ✅

### Functional Tests
- [ ] **Plugin Discovery**
  - [ ] Plugins automatically detected on startup
  - [ ] Plugin health monitoring works
  - [ ] Dynamic plugin loading

- [ ] **Photo Frame Plugin**
  - [ ] Gallery image discovery
  - [ ] Random image selection
  - [ ] Image upload via API
  - [ ] Base64 image encoding
  - [ ] Placeholder generation
  - [ ] Plugin manifest generation

- [ ] **API Endpoints**
  - [ ] `GET /api/channels/` returns photo_frame plugin
  - [ ] `GET /api/channels/photo_frame/manifest` returns capabilities
  - [ ] `POST /api/channels/photo_frame/request_image` returns random image
  - [ ] Custom plugin endpoints work via mounted routers

### Edge Cases
- [ ] **Error Handling**
  - [ ] Plugin loading failures
  - [ ] Invalid plugin configurations
  - [ ] Image generation failures
  - [ ] Empty gallery handling

---

## Configuration Requirements 🔧

### Main API Configuration
```yaml
channels:
  discovery:
    directory: "/var/opt/mimir/mimir-api/channels"
    scan_interval: 30  # seconds
plugins:
  # Embedded plugins - no service configuration needed
```

### Photo Frame Plugin Configuration
```json
{
  "id": "photo_frame",
  "name": "Photo Frame Channel",
  "version": "1.0.0", 
  "type": "embedded",
  "entry_point": "channel.py",
  "class_name": "PhotoFrameChannel",
  "config": {
    "supports_upload": true,
    "image_formats": ["jpg", "jpeg", "png", "gif"]
  }
}
```

---

## Success Criteria 🎯

### Must Have
- [x] Main API exposes only 4 channel endpoints
- [x] Photo frame works as embedded plugin
- [ ] Plugin discovery loads photo_frame correctly
- [ ] Image request returns random images from gallery
- [ ] All core plugin functionality preserved

### Nice to Have
- [ ] Graceful error handling for plugin failures
- [ ] Comprehensive error messages
- [ ] Plugin performance monitoring
- [ ] Hot plugin reloading

---

## Notes & Decisions 📝

### Architecture Decisions
- **Embedded Plugin Pattern**: Plugins load as Python modules into main API process
- **File System Discovery**: Plugins discovered by scanning for plugin.json files
- **Direct Method Calls**: No HTTP overhead, direct Python method invocation
- **FastAPI Router Integration**: Custom plugin endpoints via mounted routers

### Implementation Notes
- Photo frame plugin runs within main API process
- No separate services or port management required
- Plugin routers mounted at /api/channels/{plugin_id}/
- Shared application context and dependencies

### Open Questions
- [ ] Plugin isolation and resource limits
- [ ] Plugin error handling and recovery
- [ ] Plugin hot reloading capabilities
- [ ] Plugin dependency management

---

## Progress Tracking

**Current Status**: Phase 1 & 2 Complete ✅, Phase 3 Ready for Testing 🔄
**Next Step**: Deploy updated code and test embedded plugin system
**Target Completion**: Phase 1 ✅ Complete, Phase 2 ✅ Complete, Phase 3 Ready
**Blockers**: Need test images in gallery for complete testing

### Recent Progress (Phases 1 & 2)
- ✅ Converted from HTTP microservice to embedded plugin architecture
- ✅ Updated plugin discovery service for module loading
- ✅ Replaced HTTP proxy with direct method calls
- ✅ Created PhotoFrameChannel as embedded plugin
- ✅ Updated plugin.json for embedded configuration
- ✅ Implemented gallery management and random image selection
- ✅ Added plugin router with custom endpoints

### Next Steps
1. **Add test images** - Copy sample images to gallery directory
2. **Deploy updated code** - Push embedded plugin implementation to server
3. **Test plugin discovery** - Verify photo_frame plugin is discovered
4. **Test core endpoints** - Verify 4 main API endpoints work
5. **Test plugin functionality** - Random image selection, gallery management
