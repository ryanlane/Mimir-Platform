We seem to have two main.py files

one in api-service and another in api-service/app

we started a refactoring process and now we have to If you want, I can generate the folder skeleton, stub modules, and a trimmed `main.py` that wires everything via an app factory—just say the word and I'll drop it in.

---

# **Mimir API Refactoring Execution Plan**

## **Current State Analysis**

✅ **Good Progress Made:**
- App factory pattern partially implemented in `app/main.py`
- Modular structure started with `app/api/`, `app/core/`, `app/infrastructure/`, `app/schemas/`
- `pyproject.toml` exists with basic dependencies
- Some routers already created

❌ **Major Issues to Address:**
- Two `main.py` files causing confusion (api-service/main.py vs api-service/app/main.py)
- Massive monolithic `main.py` (5,198 lines) with mixed concerns
- Missing tooling setup (ruff, black, mypy, etc.)
- No proper settings management
- Database models mixed with business logic

## **Phase-by-Phase Execution Plan**

### **🚀 Phase 0: Immediate Foundation (Priority 1)**

**Goal**: Create clean foundation and resolve the dual main.py issue

1. **Consolidate main.py files**
   - Migrate missing functionality from `api-service/main.py` to `app/main.py`
   - Rename current `api-service/main.py` to `legacy_main.py` as backup
   - Update deployment scripts to use `app.main:app`

2. **Complete pyproject.toml setup**
   ```toml
   [tool.ruff]
   [tool.black]
   [tool.isort]
   [tool.mypy]
   [tool.pytest]
   ```

3. **Add pre-commit hooks**

4. **Create proper settings with Pydantic**
   - Move hardcoded values to `app/config.py`
   - Use `BaseSettings` for environment variables

### **🏗️ Phase 1: Project Structure Completion (Priority 1)**

**Goal**: Complete the modular structure layout

```
app/
├── core/                    # ✅ Exists, needs completion
│   ├── config.py           # ✅ Exists
│   ├── logging.py          # ❌ Create
│   ├── security.py         # ❌ Create
│   └── middleware.py       # ❌ Create
├── db/                     # ❌ Create (move from infrastructure/database)
│   ├── base.py
│   ├── models.py           # Extract from main.py
│   ├── session.py
│   └── migrations/         # Alembic setup
├── schemas/                # ✅ Exists, needs population
│   ├── channels.py
│   ├── overlays.py
│   ├── displays.py
│   └── common.py
├── services/               # ✅ Exists in core/, needs services
│   ├── channel_discovery.py
│   ├── websockets.py
│   ├── distribution.py
│   └── caching.py
└── api/                    # ✅ Exists, needs completion
    ├── deps.py
    └── routers/
        ├── channels.py     # ✅ Exists
        ├── overlays.py     # ❌ Extract from main.py
        ├── displays.py     # ❌ Extract from main.py
        ├── health.py       # ❌ Move from admin.py
        └── websockets.py   # ❌ Extract from main.py
```

### **🗄️ Phase 2: Database Layer Migration (Priority 2)**

**Goal**: Extract database models and setup proper migrations

1. **Extract SQLAlchemy models from main.py (lines ~52-200)**
   - Move to `app/db/models.py`
   - Keep relationships intact
   - Add proper constraints and indexes

2. **Setup Alembic**
   - Initialize migration environment
   - Create initial migration from existing models
   - Remove `Base.metadata.create_all()` calls

3. **Database session management**
   - Move engine/session creation to `app/db/session.py`
   - Create dependency injection for sessions

### **🛣️ Phase 3: API Router Extraction (Priority 2)**

**Goal**: Split monolithic endpoints into focused routers

1. **Overlays Router** (extract from main.py ~lines 1500-2000)
   - `/api/overlays/*` endpoints
   - Move to `app/api/routers/overlays.py`

2. **Display Clients Router** (extract from main.py ~lines 2000-3000)
   - Registration, update, assignment endpoints
   - Move to `app/api/routers/displays.py`

3. **WebSocket Router** (extract from main.py ~lines 3500-4500)
   - Connection management
   - Move to `app/api/routers/websockets.py`

### **📝 Phase 4: Schema Migration (Priority 3)**

**Goal**: Centralize Pydantic models

1. **Extract response models from main.py**
   - `DisplayClientResponse`, `PaginationMeta`, etc.
   - Standardize response patterns
   - Add camelCase aliases for frontend compatibility

### **⚙️ Phase 5: Service Layer (Priority 3)**

**Goal**: Extract business logic into services

1. **Channel Discovery Service** (extract from main.py ~lines 500-1000)
   - SRI hashing logic
   - Static file mounting
   - Configuration injection

2. **WebSocket Connection Manager** (extract from main.py ~lines 4000-4500)
   - Connection lifecycle
   - Database status updates

3. **Redis/Distribution Service**
   - Capability flags
   - Clean import handling

## **🎯 Immediate Action Items (Next 2 weeks)**

### **Week 1: Foundation**
1. ✅ **Backup current main.py**: `cp api-service/main.py api-service/legacy_main.py`
2. ✅ **Complete pyproject.toml** with all tooling
3. ✅ **Enhance app/config.py** with proper settings
4. ✅ **Create app factory improvements** in app/main.py
5. ✅ **Update deployment scripts** to use new entry point

### **Week 2: Database & Core Routers**
1. ✅ **Extract database models** to app/db/models.py
2. ✅ **Setup Alembic migrations**
3. ✅ **Create overlays router**
4. ✅ **Create displays router**
5. ✅ **Test endpoint functionality**

## **🔧 Technical Implementation Strategy**

### **Migration Approach**
1. **Incremental extraction**: Move one router at a time
2. **Maintain backward compatibility**: Keep legacy endpoints during transition
3. **Comprehensive testing**: Test each extracted component
4. **Feature flags**: Use configuration to toggle between old/new implementations

### **Risk Mitigation**
1. **Backup strategy**: Keep legacy_main.py as rollback option
2. **Parallel testing**: Run both old and new implementations temporarily
3. **Gradual deployment**: Phase rollout in development → staging → production

## **🚦 Success Metrics**

- [ ] Reduced main.py from 5,198 lines to <100 lines
- [ ] All endpoints functioning with new router structure  
- [ ] Database migrations working properly
- [ ] All tests passing
- [ ] Pre-commit hooks enforcing code quality
- [ ] Clean separation of concerns across modules

## **⚡ Quick Wins (This Week)**

1. **Resolve dual main.py confusion** - immediate developer productivity boost
2. **Add linting/formatting** - code quality improvement
3. **Extract websocket logic** - largest chunk of complexity
4. **Standardize response formats** - API consistency

## **🔄 Implementation Checklist**

### **Phase 0 - Foundation**
- [x] Backup api-service/main.py to legacy_main.py
- [x] Enhanced pyproject.toml with dev tools (ruff, black, isort, mypy, pytest)
- [x] Pre-commit hooks configuration
- [x] Complete app/config.py with BaseSettings
- [x] Update app/main.py app factory
- [x] Update deployment scripts (systemd service, README)
- [x] Create .env.example for environment configuration

### **Phase 1 - Structure**
- [x] Create app/db/ directory structure
- [x] Create missing core modules (logging.py, security.py, middleware.py)
- [x] Create missing services modules
- [x] Create app/utils/ directory (sri.py, files.py, pagination.py)
- [x] Create app/api/deps.py
- [x] Setup Alembic migrations infrastructure
- [x] Extract database models to app/db/models.py
- [x] Create app/db/base.py and session.py
- [x] Update app factory to use new structure

### **Phase 2 - Database**
- [ ] Extract models to app/db/models.py
- [ ] Create app/db/base.py and session.py
- [ ] Setup Alembic migrations
- [ ] Remove create_all() calls
- [ ] Add proper constraints and indexes

### **Phase 3 - Routers**
- [ ] Extract overlays endpoints to app/api/routers/overlays.py
- [ ] Extract display endpoints to app/api/routers/displays.py
- [ ] Extract websocket endpoints to app/api/routers/websockets.py
- [ ] Move health endpoints to app/api/routers/health.py

### **Phase 4 - Schemas**
- [ ] Move Pydantic models to app/schemas/
- [ ] Standardize response formats
- [ ] Add camelCase aliases

### **Phase 5 - Services**
- [ ] Extract ChannelDiscovery to services/channel_discovery.py
- [ ] Extract ConnectionManager to services/websockets.py
- [ ] Create distribution service with feature flags
- [ ] Create caching service

**Next Steps**: Ready to begin implementation starting with Phase 0 foundation work.igure out how to migrate code changes from the api-service/main.py to api-service/app/main.py and continue with beaking out code in the their correct buckets. We already have a good start on a few
app/api
app/core
app/infrastucture
app/schemas

Below is a plan to take care of the two main.py files and create a new better easier way to manage this project.

# FastAPI Refactor TODO (hand-off checklist)

## Phase 0 — Baseline hygiene

* [ ] Add `pyproject.toml` with tooling: `ruff`, `black`, `isort`, `mypy`, `pytest`, `pre-commit`.
* [ ] Introduce an app factory (`create_app(settings)`) so tests can inject settings and dependencies cleanly rather than using a global `app` (currently created inline) .
* [ ] Switch configuration to Pydantic Settings (`BaseSettings`) for `DATABASE_URL`, `CORS_ORIGINS`, `CHANNELS_DIR`, feature flags (e.g., Redis/Distribution). These are hardcoded/env-split today (DB/CORS/channel dir).  &#x20;

## Phase 1 — Project layout

Create an `app/` package and keep `main.py` tiny.

```
app/
  core/        # cross-cutting concerns
    config.py
    logging.py
    security.py
    middleware.py
  db/
    base.py
    models.py
    session.py
    migrations/  # Alembic
  schemas/     # Pydantic models
    channels.py
    overlays.py
    displays.py
    common.py
  services/
    channel_discovery.py
    websockets.py
    rate_limit.py
    distribution.py
    caching.py
  api/
    deps.py
    routers/
      channels.py
      overlays.py
      displays.py
      health.py
      websocket_status.py
  utils/
    sri.py
    files.py
    pagination.py
```

## Phase 2 — Database layer

* [ ] Move SQLAlchemy models out of `main.py` into `app/db/models.py`. They’re currently interleaved with business logic (Channels/Scenes/Overlays/Display\*…).  &#x20;
* [ ] Keep `Base`, engine, and `SessionLocal` in `db/base.py` & `db/session.py`. (Engine/pool is created inline now.)&#x20;
* [ ] Add Alembic migrations; stop calling `Base.metadata.create_all()` at runtime. (It’s invoked now.)&#x20;
* [ ] Add constraints & indexes (uniques on IDs where appropriate); consider FKs between `DisplayClient.assigned_scene_id` → `Scene.id` (currently plain `String`).&#x20;

## Phase 3 — API routers

* [ ] Split endpoints by resource into `api/routers/*` and register with `include_router` from `main`. You already dynamically mount channel routers—mirror that pattern for first-party routers.&#x20;
* [ ] Pull overlays endpoints into `routers/overlays.py` (currently at `/api/overlays`).&#x20;
* [ ] Split display client endpoints (register/update/assign/etc.) into `routers/displays.py`. (Registration currently in the monolith.)&#x20;
* [ ] Keep the health endpoint in `routers/health.py`, but wire redis/db checks via services; it’s already solid, just relocate.&#x20;

## Phase 4 — Schemas (Pydantic)

* [ ] Move Pydantic models (`DisplayClientResponse`, `PaginationMeta`, etc.) to `app/schemas/*`. They’re mixed in with routes right now. &#x20;
* [ ] Standardize responses (paginate consistently with the same envelope used in overlays/channels). &#x20;
* [ ] Adopt aliases/`model_config` to keep camelCase properties stable for the frontend while using snake\_case in Python.

## Phase 5 — Services

* [ ] Extract **ChannelDiscovery** into `services/channel_discovery.py`. Keep its SRI hashing and static mounts, but inject `channels_dir` from Settings. (It currently computes SRI and mounts UI.) &#x20;
* [ ] Extract **ConnectionManager** (WebSockets) into `services/websockets.py`; keep DB status updates there (they’re done directly today in `connect_display_client`).&#x20;
* [ ] Wrap **Redis/Distribution** behind capability flags in `services/distribution.py` so imports don’t scatter try/excepts in route files. (Currently guarded where used.) &#x20;
* [ ] Centralize short-TTL **cache** helper (you already cache `/api/websocket/status`). Move cache dicts and rate-limit dicts into a service.&#x20;

## Phase 6 — Middleware & dependencies

* [ ] Convert global rate limiting from a dependency into proper Starlette middleware (and/or use a dependency at the router level), rather than trying to mutate routes after creation with `add_global_rate_limiting()`. &#x20;
* [ ] Move CORS setup into `core/config.py` + `core/middleware.py`. (Currently configured inline from env.)&#x20;
* [ ] Add request ID + structured logging middleware (see next section).

## Phase 7 — Logging & observability

* [ ] Replace ad-hoc `print()` with structured logs via `logging` (JSON or key-value). A logger exists but isn’t configured globally yet.&#x20;
* [ ] Add `/metrics` (Prometheus) or basic instrumentation (timings, error counters).
* [ ] Add Sentry (optional) via middleware.

## Phase 8 — Security & validation

* [ ] AuthN/AuthZ: add API key or OAuth (minimal: per-route API key dependency). None present now.
* [ ] File-serving hardening in `get_subchannel_current_image`: prevent path traversal; validate `resolution` strictly; ensure path joins are locked to an allowed root. (It currently passes through a file path returned by a manager and infers media type.) &#x20;
* [ ] Validate channel `config.json` more strictly (JSON Schema). You already check required fields—promote to a validator service.&#x20;

## Phase 9 — Configuration & environment

* [ ] Centralize constants like `CHANNELS_DIR = "channels"` and default schema versions in `core/config.py` (currently scattered defaults). &#x20;
* [ ] Switch seed/sample data to an idempotent management command rather than running on startup (currently `init_sample_data()` executes at import time).&#x20;

## Phase 10 — Testing

* [ ] Add `pytest` suites using `TestClient`; use app factory to inject a test DB (SQLite memory or tmp file).
* [ ] Create fixtures for `Session`, seeded channels, and fake Redis manager.
* [ ] Add contract tests for dynamic channel router inclusion (assert `/api/channels/{id}` routes exist after discovery).&#x20;

## Phase 11 — Performance & reliability

* [ ] Keep SQLAlchemy pool config (you already tuned it) but move to settings so prod/dev differ.&#x20;
* [ ] Replace periodic cleanups sprinkled in request handlers with a background task or middleware tick (rate-limit cleanup happens opportunistically right now). &#x20;
* [ ] Consider `watchfiles`/hot-reload for channel discovery in dev.

## Phase 12 — API ergonomics

* [ ] Tag & group routes for docs; add examples to response models and error payloads (you’ve begun with consistent pagination and error shapes).&#x20;
* [ ] Stabilize URL versioning (`/api/v1/...`) to allow future breaking changes.

## Phase 13 — Deployment

* [ ] Add Dockerfile and `docker-compose` for local dev (DB + Redis); use `.env`.
* [ ] Add Makefile tasks: `make fmt`, `make test`, `make run`, `make migrate`.
* [ ] Healthchecks already solid—keep `/api/health` as k8s/docker health endpoints. &#x20;

---

## Quick wins (in this codebase)

* Convert the **two** rate-limit implementations (global + websocket status) into a single middleware + small per-route limiter util. &#x20;
* Move **ChannelDiscovery** + SRI hashing to `services/` and expose a clean manifest method to the router (you already have `get_manifest_for_ui()`).&#x20;
* Extract **ConnectionManager** and its DB side effects.&#x20;

If you want, I can generate the folder skeleton, stub modules, and a trimmed `main.py` that wires everything via an app factory—just say the word and I’ll drop it in.
