# Mimir FastAPI Server Architecture Summary

## Overview

**Mimir API** is a FastAPI-based content management system for coordinating multi-display digital signage. It runs as a single Python process with embedded plugins (channels), WebSocket support, MQTT integration, and a PostgreSQL/SQLite backend.

- **Stack:** FastAPI 0.116+, Uvicorn, SQLAlchemy 2.0, Pydantic 2.5
- **Entry point:** `mimir-api/app/main.py`
- **Plugins:** Dynamically loaded from `CHANNELS_DIR` with hot reload support
- **Port:** Default `5000` (HTTP/REST) + WebSocket at `/ws`
- **Base API prefix:** `/api` (configurable)

---

## API Endpoint Structure

### Core Routers & Exposed Endpoints

All routers are mounted under `/api` prefix (configured via `settings.api_prefix`):

#### 1. **Health & Admin** (`app.api.routes.admin`)

- `GET /api/health` — Health check endpoint
- `GET /api/metrics` — OpenTelemetry/Prometheus metrics
- `POST /api/admin/mqtt/test` — Test MQTT broker connectivity
- Image upload/persistence endpoints

#### 2. **Channels** (`app.api.routes.channels`)

- `GET /api/channels/` — List all available channel plugins with metadata
- `GET /api/channels/{channel_id}/manifest` — Get channel capabilities and schema
- `GET /api/channels/{channel_id}/health` — Check individual channel health
- `GET /api/channels/{channel_id}/images/{image_id}` — Retrieve channel-generated images
- **Dynamic channel routes:** Each plugin adds its own routes under `/api/channels/{channel_id}/*`
  - Example: `/api/channels/weather/request-image`, `/api/channels/spotify_status/status`

#### 3. **Scenes** (`app.api.routes.scenes`)

- `GET /api/scenes/` — List all scenes (paginated)
- `GET /api/scenes/{scene_id}` — Get scene details with schedule
- `POST /api/scenes/` — Create a new scene
- `PUT /api/scenes/{scene_id}` — Update scene
- `DELETE /api/scenes/{scene_id}` — Delete scene
- `POST /api/scenes/{scene_id}/activate` — Activate a scene immediately
- `POST /api/scenes/{scene_id}/refresh_content` — Refresh scene content
- `POST /api/scenes/{scene_id}/refresh` — Trigger content refresh

#### 4. **Displays** (`app.api.routes.displays/*`)

- `GET /api/displays/` — List all registered display clients
- `GET /api/displays/{display_id}` — Get display details & current assignment
- `POST /api/displays/{display_id}/scene` — Assign a scene to a display (via MQTT)
- `DELETE /api/displays/{display_id}/scene` — Unassign scene from display
- `POST /api/displays/{display_id}/images` — Upload persisted display images
- `GET /api/displays/{display_id}/images` — Retrieve display's rendered images
- **Provisioning & Discovery:**
  - `POST /api/displays/provision/setup` — Device bootstrap flow
  - `POST /api/displays/provision/register` — Device registration with token
  - `POST /api/displays/mdns/ingest` — Ingest external mDNS discovery events
  - `GET /api/displays/mqtt/config` — Get MQTT broker config for clients

#### 5. **Display-Scene Analytics** (`app.api.routes.display_scene`)

- `GET /api/display-scene/scenes/with-displays` — Scenes with display assignment stats
- `GET /api/display-scene/scenes/{scene_id}/displays` — Scene with assigned displays
- `GET /api/display-scene/displays/by-location` — Displays grouped by location
- `GET /api/display-scene/dashboard/overview` — Assignment dashboard data

#### 6. **Scheduler** (`app.api.routes.scheduler`)

- `POST /api/scheduler/jobs` — Create a scheduled job
- `GET /api/scheduler/jobs` — List all jobs
- `PUT /api/scheduler/jobs/{job_id}` — Update job
- `DELETE /api/scheduler/jobs/{job_id}` — Delete job
- `POST /api/scheduler/jobs/{job_id}/trigger` — Manually trigger a job
- `POST /api/scheduler/jobs/{job_id}/scenes` — Assign scene to job
- `DELETE /api/scheduler/jobs/{job_id}/scenes/{scene_id}` — Remove scene from job
- `POST /api/scheduler/jobs/bulk-operation` — Bulk operations on jobs

#### 7. **Discovery** (`app.api.routes.discovery`)

- `GET /api/displays/discovery` — List discovered devices (mDNS)
- `POST /api/displays/{device_id}/approve` — Approve device for registration
- `POST /api/displays/{device_id}/reject` — Reject device registration

#### 8. **Store & Plugin Registry** (`app.api.routes.store`)

- `GET /api/store/registry` — Fetch plugin registry from external source
- `POST /api/store/registry/refresh` — Refresh registry cache
- `GET /api/store/updates` — Check for plugin/channel updates

#### 9. **Client Releases** (`app.api.routes.client_releases`)

- `GET /api/client-releases/latest` — Get latest display client version
- `GET /api/client-releases/{version}/download` — Download specific client version

#### 10. **Overlays** (`app.api.routes.overlays`)

- `GET /api/overlays/` — List all overlays
- `GET /api/overlays/{overlay_id}` — Get overlay details
- `POST /api/overlays/` — Create overlay
- `PUT /api/overlays/{overlay_id}` — Update overlay
- `DELETE /api/overlays/{overlay_id}` — Delete overlay

#### 11. **Debug/MQTT** (`app.api.routes.debug_mqtt`)

- `POST /api/debug/mqtt/echo` — Echo test to MQTT broker
- `GET /api/debug/mqtt/stats` — Get MQTT statistics

#### 12. **WebSockets** (No `/api` prefix)

- `WS /ws` — Dashboard/generic client connection
- `WS /ws/display/{display_id}` — Display client real-time connection
- `GET /api/websocket/status` — WebSocket service status & stats

---

## Plugin/Channel Architecture

### How Plugins Integrate

Channels are **embedded plugins** loaded directly into the main API process at startup:

1. **Discovery Phase** (startup)
   - `PluginDiscoveryService` scans `CHANNELS_DIR` for `plugin.json` files
   - Each plugin must export:
     - `get_router()` → FastAPI APIRouter for custom endpoints
     - `get_manifest()` → Channel capabilities/schema
     - `request_image()` → Image generation method
     - Optional: `get_status()`, `on_startup()`, `on_shutdown()`

2. **Loading Phase**
   - Plugin module is dynamically imported
   - Router mounted at `/api/channels/{channel_id}/*`
   - Static files (if any) mounted at `/channels/{channel_id}/*`
   - Lifecycle hooks invoked

3. **Error Isolation**
   - Unhandled exceptions in plugin routes caught → 500 JSON response
   - Single plugin crash doesn't affect API server or other plugins
   - `_IsolatedPluginRoute` wraps plugin handlers

### Current Channels (Examples)

- **weather** — Fetch weather data, render to image
- **comic_covers** — Scrape comic covers, display with metadata
- **movie_posters** — Curate movie poster content
- **spotify_status** — Display current Spotify playback
- **headlines** — Fetch news headlines
- **slow_movie** — Long-duration artistic content
- **photo_frame** — Gallery/photo display

All are discoverable via `GET /api/channels/` and managed through the plugin system.

---

## Communication Patterns

### 1. Display Clients ↔ API

#### MQTT (Primary for Commands)

- **Broker:** Mosquitto (internal or external)
- **Flow:** API publishes scene assignments → displays subscribe & execute
- **Topics:**
  - `mimir/{display_id}/cmd` — Commands (scene assignment)
  - `mimir/{display_id}/status` — Display reports status/health
  - Last Will & Testament for presence detection

#### WebSocket (Real-time Feedback)

- `WS /ws/display/{display_id}` — Display keeps persistent connection
- **Events:** Status updates, render confirmations, error reports
- Used for instant feedback and monitoring

#### HTTP REST (Content Delivery)

- Displays poll `/api/scenes/{scene_id}/` for scene content
- Download images, manifests, and configuration via HTTP

### 2. External Services/Agents ↔ API

#### Direct HTTP REST

Most integrations use standard RESTful endpoints:

```bash
# List scenes
curl http://localhost:5000/api/scenes/

# Create a scene
curl -X POST http://localhost:5000/api/scenes/ \
  -H "Content-Type: application/json" \
  -d '{"name": "My Scene", "channels": [...]}'

# Assign scene to display
curl -X POST http://localhost:5000/api/scenes/{scene_id}/activate

# Get channel capabilities
curl http://localhost:5000/api/channels/{channel_id}/manifest
```

#### WebSocket (Dashboard / Real-time Monitoring)

```javascript
// Connect to dashboard endpoint
const ws = new WebSocket("ws://localhost:5000/ws");

// Receive state updates, channel status changes, display events
ws.onmessage = (event) => {
  const { event_type, data } = JSON.parse(event.data);
  // Handle update...
};

// Request state snapshot
ws.send(JSON.stringify({ event: "state_sync_request" }));
```

#### Scheduler Jobs (Deferred Execution)

External systems can create scheduled jobs that trigger scene assignments:

```bash
curl -X POST http://localhost:5000/api/scheduler/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Morning Display",
    "cron": "0 7 * * *",
    "job_type": "activate_scene"
  }'
```

---

## Current API Capabilities & Limitations

### ✅ Strengths

1. **Full Display Lifecycle Management**
   - Device discovery, pairing, provisioning, and assignment
   - MQTT presence detection + HTTP health monitoring
   - Image persistence and rendering feedback

2. **Flexible Content System**
   - Scenes compose multiple channels and overlays
   - Schedule scenes on displays or run immediately
   - Channel plugins can expose custom endpoints

3. **Real-time Monitoring**
   - WebSocket for live dashboard updates
   - Display status events, channel health checks
   - Metrics/observability via OpenTelemetry + Prometheus

4. **Plugin Architecture**
   - Hot reload during dev (via `dev_watcher_service`)
   - Error isolation — plugin crashes don't crash API
   - Dynamic router mounting — plugins define their own endpoints

### ⚠️ Current Limitations & Pain Points

1. **No Built-in Agent/LLM Integration**
   - **Gap:** No endpoints for AI-driven scene generation, recommendations, or natural language queries
   - **Workaround:** External agents must construct HTTP requests manually
   - **Example need:** "Show me weather + calendar on the lobby display" → Agent must:
     1. Parse intent → extract displays, channels, data
     2. Call `/api/channels/weather/`, `/api/channels/calendar/` separately
     3. Compose into `/api/scenes/` POST
     4. Call `/api/scenes/{id}/activate` or assign via MQTT

2. **Stateless Endpoints (No Session/Context)**
   - API requests don't carry user context or intent history
   - Each request is isolated — no "conversation" or learning
   - No way to store agent instructions, preferences, or past actions

3. **Limited Query/Filter Language**
   - Scene and display listing use simple pagination (limit/offset)
   - No complex filtering, search, or aggregation DSL
   - Agents must fetch full lists and filter locally

4. **No Bulk Mutation Transactions**
   - Scene/display assignment is request-per-assignment
   - No atomic multi-operation transactions
   - Risk of partial failures in complex workflows

5. **Image Content is Binary/Static**
   - Channel `request_image()` returns raw JPEG/PNG
   - No structured metadata with images
   - Difficult for agents to understand "what's on the display" without OCR/vision

6. **Limited Extensibility for Agent-Specific Features**
   - No webhooks/callbacks for "when scene is rendered" or "when display goes offline"
   - Agent must poll WebSocket or HTTP endpoints to react
   - No built-in audit trail or action replay

---

## Database & Models

### Core Entities (SQLAlchemy)

Located in `app/db/models.py`:

- **DisplayClient** — Registered display device (ID, hostname, IP, status)
- **Scene** — Content composition (name, layout, channel assignments, schedule)
- **SceneChannel** — Link between scene and channel with configuration
- **SceneSchedule** — Cron triggers for scene activation
- **DisplayScene** — Current scene assignment + metadata
- **DisplaySceneImage** — Persisted rendered images (for display → display replay)
- **Overlay** — UI overlays (clock, ticker, etc.)

### Migrations

Managed by Alembic (in `migrations/` directory). Schema changes tracked via numbered migration files. Auto-applied on startup via `docker-compose` entrypoint.

---

## Configuration & Deployment

### Environment Variables (Key Settings)

```bash
# Database
DATABASE_URL=postgresql://user:pass@db:5432/mimir
# Or: sqlite:///./app.db

# Paths
CHANNELS_DIR=/var/opt/mimir/channels
UPLOAD_DIR=/var/opt/mimir/mimir-api/uploads
SCHEDULER_TEMP_DIR=/var/opt/mimir/scheduler_temp

# MQTT (internal broker)
MQTT_ENABLED=true
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
MQTT_USERNAME=mimir
MQTT_PASSWORD=secure_password

# API & CORS
API_HOST=0.0.0.0
API_PORT=5000
API_PREFIX=/api
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Redis (optional, for distribution)
REDIS_ENABLED=true
REDIS_URL=redis://redis:6379/0

# mDNS Discovery
MDNS_DISCOVERY_ENABLED=true
MDNS_UPDATE_INTERVAL=30
MDNS_OFFLINE_TIMEOUT=120

# Development
DEBUG=true
LOG_LEVEL=INFO
```

### Docker Compose Stacks

- **Production:** `docker-compose.yml` — Full stack with authenticated MQTT
- **Local Dev:** `docker-compose.dev.yml` — Hot reload, anonymous MQTT
- **WSL Dev:** `docker-compose.wsl.yml` — Bridge networking workaround

---

## Key Services & Dependencies

### Core Services

| Service                  | Purpose                                                 |
| ------------------------ | ------------------------------------------------------- |
| `PluginDiscoveryService` | Load and lifecycle-manage channel plugins               |
| `SchedulerService`       | APScheduler integration for time-based jobs             |
| `WebSocketManager`       | Unified WebSocket connection pool & broadcasting        |
| `DistributionService`    | Redis-based content distribution (with memory fallback) |
| `MQTTPresenceService`    | Detect online/offline displays via MQTT LWT             |
| `DisplaySceneService`    | Queries and analytics on scene-display assignments      |
| `SceneRefreshService`    | Trigger channel content refresh on schedule/demand      |
| `MdnsDiscoveryService`   | Discover new displays on LAN via mDNS/Bonjour           |
| `PluginManager`          | Enable/disable plugins, manage dev linking              |
| `DevWatcher`             | Hot reload channels on file changes (dev only)          |
| `HtmlRendererService`    | Shared Chromium for HTML→image rendering                |

### External Service Integrations

- **Redis** — Optional, for distributed caching & pub/sub
- **PostgreSQL** — Production database (SQLite for dev)
- **Mosquitto** — MQTT broker for display control
- **zeroconf** (Python) — mDNS device discovery
- **OpenTelemetry** — Tracing & metrics export

---

## How External Agents/Services Call This API

### Pattern 1: Synchronous REST Calls (Standard)

```python
import httpx

async def assign_scene_to_display(display_id, scene_id):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"http://api:5000/api/scenes/{scene_id}/activate",
            json={"display_id": display_id}
        )
        return resp.json()
```

### Pattern 2: WebSocket Subscription (Monitoring)

```javascript
const ws = new WebSocket("ws://api:5000/ws");
ws.onmessage = (event) => {
  const { event_type, data } = JSON.parse(event.data);
  if (event_type === "channel_status_changed") {
    // React to channel going online/offline
  }
};
```

### Pattern 3: Polling (Fallback)

```bash
# Poll display status every 10s
while true; do
  curl -s http://api:5000/api/displays/{id} | jq .
  sleep 10
done
```

### Pattern 4: Scheduler Jobs (Deferred)

```bash
curl -X POST http://api:5000/api/scheduler/jobs \
  -d '{
    "name": "agent_job",
    "cron": "0 * * * *",
    "job_type": "activate_scene",
    "metadata": {"scene_id": "morning"}
  }'
```

---

## Summary: What's Missing for Agent Integration

To enable intelligent agent-driven display management, the API would benefit from:

1. **Agent Intentions Endpoint** — POST `/api/intents/` for NL queries
   - "Show weather on lobby display"
   - → API interprets, creates scene, assigns, returns result

2. **Structured Scene Templates** — GET `/api/scene-templates/` with DSL
   - Predefined layouts with pluggable channel slots
   - Agents pick template + fill slots

3. **Audit Trail & Replay** — GET `/api/audit-log/`, POST `/api/replay/`
   - Track all assignments, changes, errors
   - Replay past states for testing or recovery

4. **Webhook/Callback System** — Register callbacks for events
   - "Notify me when scene X is rendered"
   - "Alert if display Y is offline for > 5min"

5. **Bulk Transactions** — POST `/api/batch/` for atomic multi-op
   - Assign same scene to 10 displays atomically
   - Rollback on any failure

6. **Content Metadata** — Structured image + metadata responses
   - Images + extracted text, colors, objects detected
   - Agents understand content, can make smarter decisions

7. **Session/Context** — Carry agent identity + preferences across requests
   - Store agent instructions, learning state
   - Reference past operations

---

## Accessing Documentation

- **Swagger UI** (when debug=true): `http://localhost:5000/docs`
- **ReDoc** (when debug=true): `http://localhost:5000/redoc`
- **Source:** [mimir-api README](../README.md)
- **Architecture notes:** [ARCHITECTURE_REVIEW.md](../docs/ARCHITECTURE_REVIEW.md)
