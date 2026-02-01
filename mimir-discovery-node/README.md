# mimir-discovery-node (Option A)

Node-based mDNS discovery agent for Mimir using `bonjour-service`.

This is intended as a good path for **Windows developers**:

- run the Mimir core stack in Docker (even via Docker Desktop/WSL2)
- run this agent on the Windows host (outside WSL) so it can see LAN multicast

## Requirements

- Node.js 18+

## Install

From this folder:

- `npm install`

## Run

PowerShell:

- `$env:MIMIR_API_BASE='http://127.0.0.1:5000'`
- `npm start`

(You can also do one-liners in `cmd.exe`/bash, but PowerShell env is easiest to read.)

Optional token auth:

- `$env:MIMIR_DISCOVERY_TOKEN='...'`

The agent posts events to the API ingest endpoint (`discovered`, `updated` on TXT changes, and `lost`).

Service browsing settings (defaults match `_mimir-display._tcp.local.`):

- `MIMIR_MDNS_TYPE=mimir-display`
- `MIMIR_MDNS_PROTOCOL=tcp`

Discovery query refresh (re-sends the browse query periodically):

- `MIMIR_BROWSE_UPDATE_MS=30000`

If you have multiple adapters (VPN, Docker, WSL, multiple NICs) and discovery shows 0 services,
force the mDNS bind interface to your *LAN* IP:

- `MIMIR_MDNS_INTERFACE=192.168.1.28`

You can also provide a comma-separated allowlist (rare; mostly useful on multi-homed hosts):

- `MIMIR_MDNS_INTERFACE=192.168.1.28,10.0.0.5`

You can also override the mDNS port (rarely needed; default is 5353):

- `MIMIR_MDNS_PORT=5353`

Batching:

- `MIMIR_BATCH_MS=1000`

Stats logging:

- `MIMIR_STATS_MS=10000` (set to `0` to disable)

## Troubleshooting (Windows)

If the API stays at `total_discovered: 0`, first determine whether Windows can see *any* mDNS.

Run with debug + browse-all:

- `$env:LOG_LEVEL='debug'`
- `$env:MIMIR_BROWSE_ALL='true'`
- `$env:MIMIR_MDNS_INTERFACE='192.168.1.28'`  # often required on Windows
- `npm start`

Notes:

- In `LOG_LEVEL=debug`, the agent prints detected network interfaces (`[discovery] nics ...`).
- `seenCount` in `[discovery] stats` means “mDNS events received”. If it stays `0`, you’re not seeing multicast on that interface.
- `postedCount` means “events successfully ingested by the API”. If `seenCount > 0` but `postedCount = 0`, check API reachability and token settings.

Outcomes:

- If you see lots of `[discovery] up(raw)` lines but none with `type: mimir-display`, your devices may not be advertising `_mimir-display._tcp` on that LAN segment.
- If you see no `up(raw)` lines at all, Windows is not receiving mDNS multicast (often Windows Firewall, VPN, or Wi-Fi AP isolation).

## Packaging idea (future)

- Package as a single Windows executable using `pkg` or `nexe`.
