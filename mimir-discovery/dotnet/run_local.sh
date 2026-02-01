#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

: "${MIMIR_API_BASE:=http://127.0.0.1:5000}"
: "${MIMIR_MDNS_TYPE:=mimir-display}"
: "${MIMIR_MDNS_PROTOCOL:=tcp}"
: "${MIMIR_BROWSE_UPDATE_MS:=30000}"
: "${MIMIR_BATCH_MS:=1000}"
: "${MIMIR_STATS_MS:=10000}"
: "${LOG_LEVEL:=info}"

export MIMIR_API_BASE
export MIMIR_MDNS_TYPE
export MIMIR_MDNS_PROTOCOL
export MIMIR_BROWSE_UPDATE_MS
export MIMIR_BATCH_MS
export MIMIR_STATS_MS
export LOG_LEVEL

if [[ -n "${MIMIR_MDNS_INTERFACE:-}" ]]; then export MIMIR_MDNS_INTERFACE; fi
if [[ -n "${MIMIR_MDNS_PORT:-}" ]]; then export MIMIR_MDNS_PORT; fi

if [[ -n "${MIMIR_DISCOVERY_TOKEN:-}" ]]; then export MIMIR_DISCOVERY_TOKEN; fi

echo "[discovery-dotnet] Starting with:"
echo "  MIMIR_API_BASE=$MIMIR_API_BASE"
echo "  MIMIR_MDNS_TYPE=$MIMIR_MDNS_TYPE"
echo "  MIMIR_MDNS_PROTOCOL=$MIMIR_MDNS_PROTOCOL"
echo "  MIMIR_BROWSE_UPDATE_MS=$MIMIR_BROWSE_UPDATE_MS"
echo "  MIMIR_BATCH_MS=$MIMIR_BATCH_MS"
echo "  MIMIR_STATS_MS=$MIMIR_STATS_MS"
echo "  LOG_LEVEL=$LOG_LEVEL"
if [[ -n "${MIMIR_MDNS_INTERFACE:-}" ]]; then echo "  MIMIR_MDNS_INTERFACE=$MIMIR_MDNS_INTERFACE"; fi
if [[ -n "${MIMIR_MDNS_PORT:-}" ]]; then echo "  MIMIR_MDNS_PORT=$MIMIR_MDNS_PORT"; fi
if [[ -n "${MIMIR_DISCOVERY_TOKEN:-}" ]]; then echo "  MIMIR_DISCOVERY_TOKEN=***"; fi

echo "[discovery-dotnet] Running... (Ctrl+C to stop)"
exec dotnet run --project "$ROOT_DIR/Mimir.Discovery.csproj"
