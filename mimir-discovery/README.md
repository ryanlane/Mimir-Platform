# mimir-discovery

Host-network “edge” discovery service for Mimir.

- Browses mDNS/Zeroconf on the LAN for `_mimir-display._tcp.local.`
- Sends discovery events to the Mimir API over HTTP

## Environment

- `MIMIR_API_BASE` (default: `http://127.0.0.1:5000`)
- `MIMIR_DISCOVERY_TOKEN` (optional; must match API `MDNS_EXTERNAL_FEED_TOKEN` if set)
- `MIMIR_MDNS_SERVICE_TYPE` (default: `_mimir-display._tcp.local.`)
- `MIMIR_BATCH_SECONDS` (default: `1.0`)

## Compose

This service is intended to run with `network_mode: host` on Linux.

Enable it via the compose profile:

- `docker compose --profile discovery up -d --build`

## Run on the host (outside Docker)

This is the recommended approach on Docker Desktop / WSL2 environments.

Linux:

- `MIMIR_API_BASE=http://127.0.0.1:5000 ./run_local.sh`

Windows (PowerShell):

- `$env:MIMIR_API_BASE='http://127.0.0.1:5000'`
- `.\run_local.ps1`
