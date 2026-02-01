# mimir-discovery (dotnet)

.NET mDNS discovery agent for Mimir. Intended for Windows users who want a native, non-Docker option.

This agent periodically scans for `_mimir-display._tcp.local.` services and posts discovery events to the API.

## Requirements

- .NET SDK 8.0+

## Run (PowerShell)

From this folder:

- `./run_local.ps1`

If PowerShell blocks script execution, run one of these first:

- `Unblock-File .\run_local.ps1`
- `Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File`

## Environment

- `MIMIR_API_BASE` (default: `http://127.0.0.1:5000`)
- `MIMIR_DISCOVERY_TOKEN` (optional; must match API `MDNS_EXTERNAL_FEED_TOKEN` if set)
- `MIMIR_MDNS_TYPE` (default: `mimir-display`)
- `MIMIR_MDNS_PROTOCOL` (default: `tcp`)
- `MIMIR_BROWSE_UPDATE_MS` (default: `30000`)
- `MIMIR_BATCH_MS` (default: `1000`)
- `MIMIR_STATS_MS` (default: `10000`)
- `LOG_LEVEL` (default: `info`; use `debug` for verbose)

Notes:
- `MIMIR_BROWSE_ALL` is not supported in this .NET version.
- `MIMIR_MDNS_INTERFACE` and `MIMIR_MDNS_PORT` are accepted but currently best-effort (library-dependent).

## Build

- `dotnet build`

## Run directly

- `dotnet run --project ./Mimir.Discovery.csproj`
