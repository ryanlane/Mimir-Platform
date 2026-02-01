#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Defaults (can be overridden via environment)
: "${MIMIR_API_BASE:=http://127.0.0.1:5000}"
: "${MIMIR_MDNS_TYPE:=mimir-display}"
: "${MIMIR_MDNS_PROTOCOL:=tcp}"
: "${MIMIR_BROWSE_UPDATE_MS:=30000}"
: "${MIMIR_BATCH_MS:=1000}"
: "${MIMIR_STATS_MS:=10000}"

# Best-effort auto-select LAN interface IP if none provided
if [[ -z "${MIMIR_MDNS_INTERFACE:-}" ]]; then
  if command -v ip >/dev/null 2>&1; then
    IFACE_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {print $7; exit}')
    if [[ -n "${IFACE_IP:-}" ]]; then
      export MIMIR_MDNS_INTERFACE="$IFACE_IP"
    fi
  fi
fi

export MIMIR_API_BASE
export MIMIR_MDNS_TYPE
export MIMIR_MDNS_PROTOCOL
export MIMIR_BROWSE_UPDATE_MS
export MIMIR_BATCH_MS
export MIMIR_STATS_MS

if [[ ! -d node_modules ]] || [[ -z "$(ls -A node_modules 2>/dev/null)" ]]; then
  echo "[discovery-node] Installing dependencies..."
  npm install
fi

echo "[discovery-node] Starting with:"
echo "  MIMIR_API_BASE=$MIMIR_API_BASE"
echo "  MIMIR_MDNS_TYPE=$MIMIR_MDNS_TYPE"
echo "  MIMIR_MDNS_PROTOCOL=$MIMIR_MDNS_PROTOCOL"
echo "  MIMIR_BROWSE_UPDATE_MS=$MIMIR_BROWSE_UPDATE_MS"
echo "  MIMIR_BATCH_MS=$MIMIR_BATCH_MS"
echo "  MIMIR_STATS_MS=$MIMIR_STATS_MS"
if [[ -n "${MIMIR_MDNS_INTERFACE:-}" ]]; then
  echo "  MIMIR_MDNS_INTERFACE=$MIMIR_MDNS_INTERFACE"
fi
if [[ -n "${MIMIR_DISCOVERY_TOKEN:-}" ]]; then
  echo "  MIMIR_DISCOVERY_TOKEN=***"
fi

echo "[discovery-node] Running... (Ctrl+C to stop)"
exec npm start
