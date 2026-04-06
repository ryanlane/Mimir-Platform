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

**Separation of concerns in the API** — routes, services, schemas, models, and infrastructure are cleanly separated under `mimir-api/api-service/app/`.

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

**Problem:** Mosquitto is configured with anonymous access. Any device on the network can publish or subscribe to any topic.

**Recommendation:** Add a commented-out auth configuration block in `mosquitto/mosquitto.conf` and document the steps to enable it. For a local/home deployment this may be acceptable, but it should be a deliberate, documented choice rather than an overlooked default.

---

### 5. Automatic Alembic Migrations on Startup

**Problem:** The API runs `alembic upgrade head` at container start. This is fine for a single-instance local setup, but could cause issues if two API containers start simultaneously (both attempt to migrate) or if a migration fails and the API starts in a partially-migrated state.

**Recommendation:** For current usage (single-instance local + deploy) this is fine to keep. Consider adding prominent error logging if the migration step fails so the root cause is immediately visible. A separate `mimir-migrate` one-shot service in compose is the cleaner long-term pattern.

---

### 6. Upload Volume Has No Backup Strategy

**Problem:** User uploads live in the `mimir_api_uploads` named Docker volume. If the volume is deleted or the host is lost, all uploaded content is gone. There is no documented backup procedure.

**Recommendation:** Document how to back up and restore the `mimir_api_uploads` volume. Consider switching to a bind mount (e.g., `./data/uploads:/var/opt/mimir/mimir-api/uploads`) so upload data lives in the project directory and is trivially backed up alongside the rest of the project.

---

### 7. CORS Origins Are Hardcoded for Localhost

**Problem:** `CORS_ORIGINS` in the env file lists only `localhost:8080` and `localhost:3000`. Accessing the service from another machine on the LAN (by IP or hostname) will fail CORS checks without manual env file editing.

**Recommendation:** Document this clearly. Consider adding a `CORS_ORIGINS_EXTRA` env var that appends to the default list so users can extend origins without replacing the entire string.

---

### 8. Frontend API URL Is Implicit

**Problem:** If the React app calls the API via `localhost` or a hardcoded address, it breaks when accessed from any other machine on the network.

**Recommendation:** Ensure the frontend API base URL is driven by a `REACT_APP_API_URL` environment variable (or equivalent), and document the correct value to set for LAN deployments.

---

### 9. mDNS / Bonjour Discovery Is Fundamentally Constrained Inside Docker

**Problem:** mDNS uses multicast (UDP `224.0.0.251:5353`). Docker's bridge network does not forward multicast between the container network and the host's physical NIC. LAN devices broadcasting via Bonjour/mDNS are invisible to containers by default.

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
| Device self-registration via MQTT or HTTP | Yes | Yes | Low — requires device-side support |

**Recommendation:** The current approach — an optional external discovery agent that calls back to the API via `MDNS_EXTERNAL_FEED_ENABLED` — is the correct one for a Docker + WSL2 environment. mDNS-based passive discovery should be treated as a convenience feature for native Linux deployments, not a core reliability path.

The more robust long-term direction for zero-config device onboarding is **MQTT self-registration**: devices publish their identity to a well-known topic on connect, and the API registers them automatically. This works entirely within Docker's network model and has no dependency on multicast or host networking.

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
| MQTT security | Anonymous by default, undocumented |
| Data persistence / backup | No strategy documented |
| LAN / remote deployment | Needs CORS + API URL guidance |
| DB migrations | Fine for current use, brittle at scale |
| mDNS discovery in Docker | Fundamentally limited; external agent is the right path |

---

## Priority Actions

1. Remove or archive the unused Node.js and .NET discovery implementations in `mimir-discovery/`
2. Flatten `mimir-api/api-service/` → `mimir-api/`
3. Document default credentials and how to override CORS origins and API URL for LAN deployments
4. Switch uploads to a bind mount so data is easy to locate and back up
5. Add a comment block to `mosquitto/mosquitto.conf` showing how to enable authentication
6. Treat mDNS as a Linux-only convenience feature; invest in MQTT self-registration as the primary device onboarding path
