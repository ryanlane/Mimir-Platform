# Mimir Plugin Architecture - Implementation TODO

## Project Status: PHASE 1 IN PROGRESS

**Objective**: Replace current tightly-coupled channel system with clean plugin architecture

**Key Deliverable**: 4-endpoint main API that proxies to independent channel services

---

## Phase 1: Core API Infrastructure 🔧 - IN PROGRESS

### Main API Changes
- [x] **Replace channels.py**
  - [x] Remove all existing channel endpoints (subchannels, settings, images, etc.)
  - [x] Implement new 4-endpoint structure
  - [x] Add HTTP client for proxying requests (using httpx)
  - [x] Handle request/response transformation

- [x] **Channel Discovery Service**
  - [x] Create new plugin_discovery.py service
  - [x] File system scanning for channel directories (plugin.json detection)
  - [x] Channel service detection and health monitoring
  - [x] Dynamic channel registry management
  - [x] Configuration loading

- [x] **HTTP Proxy Implementation**
  - [x] Request routing to channel services
  - [x] Error handling and fallback logic
  - [x] Request/response logging
  - [x] Timeout handling

- [x] **API Endpoint Implementation**
  ```
  GET /api/channels/               -> List all discovered channels ✅
  GET /api/channels/{id}/manifest  -> Proxy to channel manifest endpoint ✅
  GET /api/channels/{id}/health    -> Proxy to channel health endpoint ✅
  POST /api/channels/{id}/request_image -> Proxy to channel image request ✅
  ```

### Infrastructure Updates
- [x] **Dependencies**
  - [x] Add HTTP client library (httpx already available)
  - [x] Update FastAPI routing
  - [x] Add proxy middleware

- [x] **Configuration**
  - [x] Channel directory configuration (uses existing settings)
  - [x] Service discovery settings (integrated)
  - [x] Proxy timeout settings (30s default)

---

## Phase 2: Photo Frame Channel Conversion 📸 - IN PROGRESS

### Standalone Service Creation
- [x] **Extract Photo Frame Logic**
  - [x] Create service.py wrapper for PhotoFrameChannel
  - [x] Remove dependencies on main API services
  - [x] Implement standalone FastAPI application
  - [x] Create independent configuration system (plugin.json)

- [x] **Channel Endpoints Implementation**
  - [x] `GET /manifest` - Dynamic manifest generation with current galleries
  - [x] `POST /request_image` - Image generation with gallery options
  - [x] `GET /health` - Service health status
  - [x] `GET /ui/manage.esm.js` - UI component serving (via static mount)
  - [x] `GET /assets/*` - Static asset serving (via static mount)

- [ ] **Manifest Generation Logic**
  - [x] Query current galleries from database
  - [x] Generate imageEndpoints dynamically
  - [x] Include current option values per gallery
  - [x] Provide options_source URLs for configuration
  - [ ] Test manifest generation with real data

### Gallery Options Endpoints
- [ ] **Option Source Implementation**
  ```
  GET /galleries/{gallery_id}/options/order_mode      -> ["added", "random", "custom"]
  GET /galleries/{gallery_id}/options/crop_mode       -> ["smart_crop", "fit", "fill"]
  GET /galleries/{gallery_id}/options/update_interval_unit -> ["seconds", "minutes", "hours"]
  ```

### Asset Management
- [x] **Static Asset Serving**
  - [x] Move thumbnail serving to channel service (via proxy)
  - [x] Update asset URLs to new structure
  - [x] Ensure proper MIME type handling
  - [x] Implement caching headers

### UI Component Updates
- [ ] **Update manage.esm.js**
  - [ ] Update API base URLs to use new proxy endpoints
  - [ ] Test component loading via main API proxy
  - [ ] Ensure proper error handling

---

## Phase 3: Integration & Testing 🔬

### Service Integration
- [ ] **Channel Service Startup**
  - [ ] Create startup scripts for photo frame service
  - [ ] Configure service discovery
  - [ ] Test main API <-> channel communication

- [ ] **End-to-End Testing**
  - [ ] Test channel listing
  - [ ] Test manifest generation with multiple galleries
  - [ ] Test image request flow
  - [ ] Test UI component loading
  - [ ] Test asset serving (thumbnails, etc.)

### Data Migration
- [ ] **Existing Data Compatibility**
  - [ ] Ensure existing galleries/images work with new system
  - [ ] Migrate any configuration format changes
  - [ ] Test with existing photo frame deployments

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
- [ ] **Channel Discovery**
  - [ ] Channels automatically detected on startup
  - [ ] Channel health monitoring works
  - [ ] Dynamic channel addition/removal

- [ ] **Photo Frame Channel**
  - [ ] Gallery creation/deletion via UI
  - [ ] Image upload and thumbnail generation
  - [ ] Gallery settings management
  - [ ] Cover image setting
  - [ ] Image reordering
  - [ ] Image deletion

- [ ] **API Endpoints**
  - [ ] `GET /api/channels/` returns photo frame channel
  - [ ] `GET /api/channels/com.epaperframe.photoframe/manifest` returns dynamic galleries
  - [ ] `POST /api/channels/com.epaperframe.photoframe/request_image` generates images
  - [ ] Asset serving works for thumbnails and UI components

### Edge Cases
- [ ] **Error Handling**
  - [ ] Channel service unavailable
  - [ ] Invalid manifest responses
  - [ ] Image generation failures
  - [ ] Network timeouts

---

## Configuration Requirements 🔧

### Main API Configuration
```yaml
channels:
  discovery:
    directory: "/path/to/channels"
    scan_interval: 30  # seconds
    health_check_interval: 60  # seconds
  proxy:
    timeout: 30  # seconds
    retries: 3
```

### Photo Frame Service Configuration
```yaml
service:
  host: "localhost"
  port: 8001
  database_url: "sqlite:///photoframe.db"
storage:
  uploads_dir: "/data/uploads"
  thumbnails_dir: "/data/thumbnails"
```

---

## Success Criteria 🎯

### Must Have
- [ ] Main API exposes only 4 channel endpoints
- [ ] Photo frame works as independent service
- [ ] UI management interface loads correctly
- [ ] Image uploads and gallery management functional
- [ ] Thumbnail serving works via new asset paths
- [ ] All existing photo frame features preserved

### Nice to Have
- [ ] Graceful degradation when channels unavailable
- [ ] Comprehensive error messages
- [ ] Performance monitoring
- [ ] Automated service discovery

---

## Notes & Decisions 📝

### Architecture Decisions
- **HTTP Proxy Pattern**: Main API proxies all requests to channel services
- **File System Discovery**: Channels discovered by scanning directory structure
- **Independent Services**: Each channel runs as separate HTTP service
- **Dynamic Manifests**: Manifests generated at request time, not static files

### Implementation Notes
- Photo frame service will run on separate port (8001)
- Main API will proxy requests to http://localhost:8001
- Asset URLs change from `/api/channels/.../assets/...` to proxied channel paths
- UI components loaded via proxy to maintain consistent base URLs

### Open Questions
- [ ] Service startup coordination (Docker Compose?)
- [ ] Channel service port assignment strategy
- [ ] Error handling when channel services unavailable
- [ ] Monitoring and logging across services

---

## Progress Tracking

**Current Status**: Phase 1 Complete ✅, Phase 2 In Progress 🔄
**Next Step**: Test integration and fix any issues
**Target Completion**: Phase 1 ✅ Complete, Phase 2 80% complete
**Blockers**: Need to test end-to-end functionality

### Recent Progress (Phase 1)
- ✅ Created new plugin discovery service with httpx
- ✅ Replaced channels.py with 4-endpoint proxy architecture
- ✅ Updated dependency injection for plugin discovery
- ✅ Created photo frame standalone service wrapper
- ✅ Added plugin.json configuration for photo frame
- ✅ Implemented manifest generation with dynamic gallery endpoints
- ✅ Added health check and image request endpoints

### Next Steps
1. **Test new API endpoints** - Verify the 4 core endpoints work
2. **Start photo frame service** - Run standalone service on port 8001
3. **Test plugin discovery** - Ensure main API discovers the photo frame plugin
4. **Test manifest generation** - Verify dynamic gallery endpoints
5. **Test image requests** - End-to-end image generation flow
