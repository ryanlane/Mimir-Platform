# Architectural Review

## Overview

Mimir is a multi-tier application for managing displays, scenes, and channels. The goal is for all components — API, frontend, and supporting services — to be fully managed via Docker Compose for easy local development and deployment.

### Service Map

```
mimir-api/         → Python FastAPI backend
mimir-web/         → React SPA frontend
mimir-discovery/   → mDNS device discovery sidecar
mosquitto/         → MQTT broker config
pgadmin/           → DB admin tool config
docker-compose.yml          → Production
docker-compose.dev.yml      → Development (hot reload)
```

The core Docker Compose startup dependency chain:

```
db + redis + mqtt → api → web
```

`discovery` and `pgadmin` are behind compose profiles, keeping them opt-in.

---

## What's Working Well

**Separation of concerns in the API** — routes, services, schemas, models, and infrastructure are cleanly separated under `mimir-api/app/`.

**Dev/prod parity** — the dev compose override pattern (source mounts, polling-based file watching, dev servers) is the right approach and is well executed.

**Plugin architecture** — dynamic channel loading from a `CHANNELS_DIR` with dev linking is flexible and easy to extend.

**Observability** — OpenTelemetry + Prometheus metrics are built in from the start.

**Health checks with ordered startup** — all services define health checks and use `depends_on: { condition: service_healthy }`, avoiding race conditions on startup.

---

## Issues & Recommendations

### 1. Unused Code in `mimir-discovery/`

**Resolved:** Deleted `mimir-discovery/nodejs/` and `mimir-discovery/dotnet/`. Only the Python implementation remains, which is the canonical version wired into compose. Note: `nodejs/node_modules` and `dotnet/obj/` had been committed before `.gitignore` rules were in place — both are now covered.

---

### 2. Nested Directory Structure in `mimir-api/`

**Resolved:** Flattened `mimir-api/api-service/` into `mimir-api/`. As part of this, removed accumulated outer-level cruft (legacy ad-hoc test scripts, old standalone compose file, stale utility scripts, debug tools). Useful files (`prometheus.yml`, `mimir-api.service.example`, non-archive docs) were moved into the flattened directory. All references updated in `docker-compose.yml`, `docker-compose.dev.yml`, `.gitignore`, and READMEs.

---

### 3. Default Credentials Committed to Repo

**Decision:** Accepted as-is. This is a fully self-contained, self-hosted project. The committed credentials are sensible defaults that users are expected to update for their own deployment. No action needed.

---

### 4. MQTT Has No Authentication

**Resolved:** Anonymous access is kept as the default (appropriate for local/home deployments), but `mosquitto/mosquitto.conf` now includes a full step-by-step comment block explaining how to generate a password file, enable `password_file` auth, mount it in compose, and set the corresponding `MQTT_USER`/`MQTT_PASSWORD` env vars in the API service.

---

### 5. Automatic Alembic Migrations on Startup

**Resolved:** `set -e` was already in place so a migration failure halts the container rather than starting the API in a broken state. Added explicit `echo` log lines around the migration step in both `docker-compose.yml` and `docker-compose.dev.yml` so failures are immediately visible in container logs.

---

### 6. Upload Volume Has No Backup Strategy

**Resolved:** Switched from the `mimir_api_uploads` named Docker volume to a bind mount at `./data/uploads`. Upload data now lives in the project directory alongside the repo, making it easy to include in any backup or rsync strategy. A `.gitignore` keeps the directory tracked in git without committing its contents.

---

### 7. CORS Origins Are Hardcoded for Localhost

**Resolved:** Added `CORS_ORIGINS_EXTRA` support to `app/config.py`. It is parsed the same way as `CORS_ORIGINS` (comma-separated or JSON array) and appended to the base list without replacing it. Documented with an example in `mimir-api.docker.env`. LAN or remote deployments can now set `CORS_ORIGINS_EXTRA=http://192.168.1.50:8080` without touching the default list.

---

### 8. Frontend API URL Is Implicit

**Resolved:** The runtime URL detection logic was already solid (uses `window.location.hostname` when not on localhost, handles HTTPS). Two fixes applied:
- Added `REACT_APP_API_URL` as the priority-1 check in `getApiBaseUrl()` so build/deploy-time configuration is possible without the Settings UI
- Replaced a hardcoded stale IP as the final fallback with `http://localhost:5000/api`
- Added `REACT_APP_API_URL` as a commented example in the `web` service in `docker-compose.yml`

For LAN deployments, users can either set `REACT_APP_API_URL=http://<host>:5000` in compose, or use the API URL field in the Settings page at runtime.

---

### 9. mDNS / Bonjour Discovery Is Fundamentally Constrained Inside Docker

**Context:** mDNS uses multicast (UDP `224.0.0.251:5353`). Docker's bridge network does not forward multicast between the container network and the host's physical NIC. LAN devices broadcasting via Bonjour/mDNS are invisible to containers by default.

On WSL2 + Docker Desktop (the primary dev environment), the problem is compounded — there are three network boundaries between a container and a LAN device:

```
Physical LAN device
      ↓  mDNS multicast — works here
Windows host NIC
      ↓  WSL2 virtual switch — multicast often dropped
WSL2 VM network
      ↓  Docker bridge — multicast not forwarded
Container
```

Even `network_mode: host` only places the container on the WSL2 VM's network, not the Windows host's physical NIC. This is why the discovery sidecar is disabled by default in compose and why external discovery agent docs exist (`MDNS_EDGE_DISCOVERY.md`, `WINDOWS_MDNS_FIREWALL.md`).

**The available approaches and their trade-offs:**

| Approach | Works on WSL2? | Works on native Linux? | Complexity |
|----------|---------------|----------------------|------------|
| Discovery sidecar in compose (`network_mode: host`) | No | Yes | Low |
| External discovery agent (run on Windows host natively) | Yes | Yes | Medium — requires a host process |
| mDNS reflector/proxy (avahi reflector, mdns-repeater) | No | Fragile | High |
| Device self-registration via MQTT | Yes | Yes | Low — requires device-side support |

**Status:** The MQTT self-registration path is already fully implemented in `app/services/mqtt/registration.py`. Devices can publish to `mimir/registry/v1/register` with their identity and capabilities; the API upserts them in the database, replies with an assigned ID, and sends a `finalize_registration` command back. This flow works entirely within Docker's network model with no dependency on multicast or host networking.

mDNS passive discovery remains available as a convenience for native Linux deployments via the optional external discovery sidecar (`MDNS_EXTERNAL_FEED_ENABLED`). For all other environments, MQTT self-registration is the recommended onboarding path.

---

## Summary

| Area | Status |
|------|--------|
| Service separation | Good |
| Dev workflow | Good |
| Compose health checks | Good |
| Plugin architecture | Good |
| Discovery service | Resolved — unused Node.js and .NET implementations removed |
| Directory depth in `mimir-api/` | Resolved — flattened, cruft removed |
| Secrets / credentials | Accepted — self-hosted, user-managed defaults |
| MQTT security | Resolved — anonymous default kept, auth steps documented in mosquitto.conf |
| Data persistence / backup | Resolved — uploads moved to ./data/uploads bind mount |
| LAN / remote deployment | Resolved — CORS_ORIGINS_EXTRA added; REACT_APP_API_URL supported; stale IP fallback removed |
| DB migrations | Acceptable — `set -e` halts on failure; log lines added for visibility |
| mDNS discovery in Docker | Already solved — MQTT self-registration fully implemented; mDNS is optional convenience |

---

## Completed Actions

All items from the original review have been addressed:

1. ✅ Removed unused Node.js and .NET discovery implementations from `mimir-discovery/`
2. ✅ Flattened `mimir-api/api-service/` → `mimir-api/`; removed outer-level cruft and legacy tests
3. ✅ Default credentials accepted as-is (self-hosted); `CORS_ORIGINS_EXTRA` added for LAN origins; `REACT_APP_API_URL` supported for deploy-time API URL override
4. ✅ Uploads moved from named Docker volume to `./data/uploads` bind mount
5. ✅ `mosquitto/mosquitto.conf` now includes step-by-step auth setup instructions
6. ✅ MQTT self-registration was already fully implemented in `app/services/mqtt/registration.py`
