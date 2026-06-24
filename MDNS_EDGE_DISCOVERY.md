# mDNS discovery in Docker (why it’s tricky)

mDNS/Zeroconf is **link-local multicast**:

- UDP `5353`
- IPv4 multicast `224.0.0.251`
- IPv6 multicast `ff02::fb`

Docker’s default bridge networking often does **not** forward multicast cleanly, and Docker Desktop / WSL2 in particular can make LAN multicast discovery **flaky or impossible**. This can lead to long debugging sessions where everything looks “correct” but discovery never works.

## Recommended architecture (Linux-first)

Keep the core stack (db/redis/api/web) on normal Docker networking.

Add a small **host-network “edge” service** whose only job is:

- browse mDNS on the LAN
- report results to the API over HTTP

This keeps isolation for Postgres/Redis/etc. while making mDNS behave like it would natively.

## How Mimir implements this

### 1) API runs in “external feed” mode

The API container does **not** join multicast. Instead it:

- keeps an in-memory discovery cache (same shape as the native mDNS service)
- accepts discovery events via `POST /api/displays/mdns/ingest`

This is enabled by:

- `MDNS_DISCOVERY_ENABLED=false`
- `MDNS_EXTERNAL_FEED_ENABLED=true`

Optionally require a shared secret:

- `MDNS_EXTERNAL_FEED_TOKEN=...`

### 2) The discovery sidecar runs on host networking (Linux)

The discovery sidecar uses `network_mode: host` and can reliably listen/browse multicast on Linux.

Compose includes this service behind an opt-in profile:

- `--profile discovery`

This is intentional: users who don’t need discovery (or are on platforms where it won’t work) can keep the default setup simple.

## Usage

### Linux

Dev:

- `docker compose -f docker-compose.dev.yml --profile discovery up -d --build`

Prod-ish:

- `docker compose -f docker-compose.yml --profile discovery up -d --build`

If you set `MDNS_EXTERNAL_FEED_TOKEN` for the API, also set:

- `MIMIR_DISCOVERY_TOKEN` for the discovery sidecar

### Windows / macOS / WSL2

mDNS discovery from containers may not work reliably due to virtualization and multicast limitations.

Recommended options:

- Run the discovery process **natively on the host** (outside Docker) and point it at the API (`MIMIR_API_BASE=http://127.0.0.1:5000`).
- Use non-mDNS discovery mechanisms (e.g. MQTT presence/discovery, static configuration, or manual registration), depending on your client/device.

### Windows developer setup (no Linux server)

Best option: run discovery on **Windows** (not inside WSL).

- Keep the stack running normally in Docker/WSL (API published on `http://127.0.0.1:5000`).
- Run the discovery process on the Windows host so it can receive LAN multicast.

Preferred implementation (Option A): Node + `bonjour-service`

This is a good Windows-native path and matches what the Electron client already uses.

From `service/mimir-discovery-node` (PowerShell):

- `npm install`
- `$env:MIMIR_API_BASE='http://127.0.0.1:5000'`
- `$env:MIMIR_MDNS_INTERFACE='192.168.1.x'`  # common fix on Windows if you have VPN/Docker/WSL adapters
- `npm start`

If discovery still finds 0 devices on Windows, see:

- `WINDOWS_MDNS_FIREWALL.md`

Fallback implementation (Option B): Python + `zeroconf`

From `service/mimir-discovery` (PowerShell):

- `$env:MIMIR_API_BASE='http://127.0.0.1:5000'`
- `.\run_local.ps1`

If discovery still finds 0 devices on Windows, it is usually a firewall or network isolation issue.
Things to check:

- Windows Firewall allows UDP 5353 multicast (mDNS).
- You are on a LAN segment that permits multicast (some guest Wi-Fi / “AP isolation” networks block it).

Fallback options for Windows dev:

- Run the whole stack in a small Linux VM with **bridged networking** (so mDNS works normally), then access the UI from Windows.
- Skip mDNS during development and use a non-mDNS discovery mechanism (MQTT discovery, static config, or manual registration).

## Running discovery outside Docker (recommended for Docker Desktop/WSL2)

The discovery implementation lives in `service/mimir-discovery` and can be run directly with Python.

From `service/mimir-discovery`:

Linux:

- `MIMIR_API_BASE=http://127.0.0.1:5000 ./run_local.sh`

Windows (PowerShell):

- `cd service/mimir-discovery`
- `$env:MIMIR_API_BASE='http://127.0.0.1:5000'`
- `.\run_local.ps1`

If the API requires a token (`MDNS_EXTERNAL_FEED_TOKEN`), also set:

- `MIMIR_DISCOVERY_TOKEN`

## Why not `network_mode: host` for the whole stack?

- Avoids punching host networking holes into your entire platform
- Keeps Postgres/Redis private and isolated
- Lets you swap discovery mechanisms later (BLE/USB/static config/etc.) without touching core services
