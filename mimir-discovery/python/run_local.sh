#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate

pip install -r requirements.txt

# Example:
#   MIMIR_API_BASE=http://127.0.0.1:5000 MIMIR_DISCOVERY_TOKEN=... ./run_local.sh

exec python -m mimir_discovery
