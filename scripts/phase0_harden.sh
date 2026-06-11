#!/usr/bin/env bash
set -euo pipefail
#
# Mimir Phase 0 hardening — run ON THE PRODUCTION SERVER from the repo root:
#   bash scripts/phase0_harden.sh
#
# What it does:
#   1. Generates strong secrets and writes them into .env (POSTGRES_PASSWORD,
#      MQTT_USER/MQTT_PASSWORD, MQTT_EXPOSE_CREDENTIALS=true; ensures
#      MQTT_PUBLIC_PORT=1883). Existing non-default values are kept.
#   2. Generates mosquitto/passwd via mosquitto_passwd (docker).
#   3. Rotates the password of the EXISTING Postgres database (ALTER USER),
#      since POSTGRES_PASSWORD only applies to fresh volumes.
#   4. Recreates the stack (localhost-bound DB/Redis/pgAdmin ports, MQTT auth
#      on the LAN listener, anonymous localhost listener on 1884).
#   5. Verifies: LAN ports, anonymous-MQTT rejection, API health.
#
# Display fleet note: displays that re-bootstrap fetch the new MQTT
# credentials automatically (MQTT_EXPOSE_CREDENTIALS=true). A display that
# stays disconnected after ~2 minutes may need a restart (it re-runs
# bootstrap on boot) or scripts/setup_connection.sh as a last resort.

cd "$(dirname "${BASH_SOURCE[0]}")/.."

info() { printf '\033[36m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[WARN]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[ERR]\033[0m %s\n' "$*" >&2; exit 1; }

[ -f docker-compose.yml ] || die "run from the mimir-server repo root"
command -v docker >/dev/null || die "docker not found"
[ -f .env ] || { warn ".env not found — creating from .env.hybrid.example"; cp .env.hybrid.example .env; }

# ---------- helpers ----------
get_env() { grep -E "^${1}=" .env | head -n1 | cut -d= -f2- || true; }
set_env() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env
  else
    printf '%s=%s\n' "$key" "$val" >> .env
  fi
}
gen_secret() { openssl rand -base64 24 | tr -d '/+=' | cut -c1-24; }

# ---------- 1. secrets in .env ----------
PG_PASS="$(get_env POSTGRES_PASSWORD)"
if [ -z "$PG_PASS" ] || [ "$PG_PASS" = "mimir" ] || [ "$PG_PASS" = "change-me" ]; then
  PG_PASS="$(gen_secret)"
  set_env POSTGRES_PASSWORD "$PG_PASS"
  info "generated POSTGRES_PASSWORD"
else
  info "keeping existing POSTGRES_PASSWORD"
fi

MQTT_USER_VAL="$(get_env MQTT_USER)"
[ -n "$MQTT_USER_VAL" ] && [ "$MQTT_USER_VAL" != "change-me" ] || { MQTT_USER_VAL="mimir-display"; set_env MQTT_USER "$MQTT_USER_VAL"; }

MQTT_PASS_VAL="$(get_env MQTT_PASSWORD)"
if [ -z "$MQTT_PASS_VAL" ] || [ "$MQTT_PASS_VAL" = "change-me" ]; then
  MQTT_PASS_VAL="$(gen_secret)"
  set_env MQTT_PASSWORD "$MQTT_PASS_VAL"
  info "generated MQTT_PASSWORD"
else
  info "keeping existing MQTT_PASSWORD"
fi

set_env MQTT_EXPOSE_CREDENTIALS "true"
set_env MQTT_PUBLIC_PORT "1883"   # critical: 1884 is localhost-only
chmod 600 .env

# ---------- 2. mosquitto password file ----------
info "writing mosquitto/passwd for user '$MQTT_USER_VAL'"
rm -rf mosquitto/passwd   # in case a previous compose run created a directory
docker run --rm -v "$(pwd)/mosquitto:/work" eclipse-mosquitto:2 \
  mosquitto_passwd -c -b /work/passwd "$MQTT_USER_VAL" "$MQTT_PASS_VAL"
sudo chown "$(id -u):$(id -g)" mosquitto/passwd 2>/dev/null || true
chmod 644 mosquitto/passwd

# ---------- 3. rotate existing Postgres password ----------
if docker ps --format '{{.Names}}' | grep -q '^mimir-db$'; then
  info "rotating password on existing database"
  docker exec mimir-db psql -U mimir -d mimir \
    -c "ALTER USER mimir WITH PASSWORD '${PG_PASS}';" >/dev/null
else
  warn "mimir-db not running — password applies on next fresh start (or rerun this script with the stack up)"
fi

# ---------- 4. recreate the stack ----------
info "recreating stack with hardened config"
docker compose up -d --force-recreate db redis mqtt api web

# ---------- 5. verify ----------
info "waiting for API health..."
for i in $(seq 1 30); do
  curl -fsS http://127.0.0.1:5000/api/health >/dev/null 2>&1 && break
  sleep 2
  [ "$i" = 30 ] && die "API did not become healthy — check: docker compose logs api"
done
info "API healthy"

info "verifying anonymous MQTT is rejected on 1883..."
if docker run --rm --network host eclipse-mosquitto:2 \
     mosquitto_pub -h 127.0.0.1 -p 1883 -t mimir/test -m x 2>/dev/null; then
  die "anonymous publish on 1883 SUCCEEDED — auth is not active, check mosquitto logs"
else
  info "anonymous publish rejected ✓"
fi

info "verifying authenticated MQTT works on 1883..."
docker run --rm --network host eclipse-mosquitto:2 \
  mosquitto_pub -h 127.0.0.1 -p 1883 -u "$MQTT_USER_VAL" -P "$MQTT_PASS_VAL" \
  -t mimir/test -m x || die "authenticated publish failed"
info "authenticated publish OK ✓"

info "LAN-listening ports (should NOT include 5432/6379/5050 on 0.0.0.0):"
ss -tlnp 2>/dev/null | grep -E ':(5432|6379|5050|1883|1884|5000|8080)\s' || true

cat <<EOF

Done. Summary:
  - .env updated (chmod 600): POSTGRES_PASSWORD, MQTT_USER, MQTT_PASSWORD,
    MQTT_EXPOSE_CREDENTIALS=true, MQTT_PUBLIC_PORT=1883
  - mosquitto/passwd generated (gitignored)
  - Postgres password rotated on the live DB
  - Stack recreated: DB/Redis/pgAdmin bound to 127.0.0.1; MQTT auth on 1883

Displays will pick up credentials on their next bootstrap. Watch the fleet:
  task mqtt:sub        # presence messages on the localhost listener
If a display stays offline: power-cycle it first; setup_connection.sh second.

pgAdmin (if used): now only reachable via SSH tunnel:
  ssh -L 5050:127.0.0.1:5050 $(whoami)@<server>
EOF
