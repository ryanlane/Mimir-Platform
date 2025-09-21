#!/bin/bash
# Dedicated Database Migration Script for Mimir API
# -----------------------------------------------------------------------------
# Goals:
#  • Provide a safer, predictable, repeatable way to apply Alembic migrations.
#  • Reduce risk of accidental drift (missing columns like scenes.update_strategy).
#  • Offer optional auto-baselining for legacy DBs that predate Alembic tracking.
#  • Perform pre-flight introspection, backups (SQLite), and post-migration validation.
#  • Keep logic independent from deploy actions (service restart, rsync, etc.).
# -----------------------------------------------------------------------------
# Usage:
#   ./api-service/db_migrate.sh [options]
#
# Options:
#   --env-file <path>      Path to env file to source (default: /etc/mimir/mimir-api.env if exists)
#   --no-backup            Skip automatic SQLite file backup
#   --dry-run              Show planned actions but do not execute upgrade
#   --auto-baseline        If no alembic_version row exists but tables do, stamp current head
#   --expect-push-columns  Enforce presence of push columns (update_strategy, push_fallback_poll_seconds)
#   --help                 Show this help
#
# Exit Codes:
#   0 success
#   1 generic failure
#   2 validation / drift detected (manual action required)
#
# Notes:
#  • Script assumes being run from repository root (where app/ and alembic.ini live)
#  • Supports SQLite primarily; will attempt generic logic for PostgreSQL/MySQL if configured
#  • Does NOT restart the service. Run deploy.sh or systemctl separately after success.
# -----------------------------------------------------------------------------
set -euo pipefail
IFS=$'\n\t'

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log(){ echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"; }
ok(){ echo -e "${GREEN}✅ $*${NC}"; }
warn(){ echo -e "${YELLOW}⚠️  $*${NC}"; }
fail(){ echo -e "${RED}❌ $*${NC}"; exit 1; }

# --------------------------- Arg Parsing -------------------------------------
ENV_FILE="/etc/mimir/mimir-api.env"
DO_BACKUP=1
DRY_RUN=0
AUTO_BASELINE=0
EXPECT_PUSH_COLUMNS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2;;
    --no-backup) DO_BACKUP=0; shift;;
    --dry-run) DRY_RUN=0; DRY_RUN=1; shift;;
    --auto-baseline) AUTO_BASELINE=1; shift;;
    --expect-push-columns) EXPECT_PUSH_COLUMNS=1; shift;;
    --help|-h)
      grep '^# ' "$0" | sed 's/^# //'
      exit 0;;
    *) fail "Unknown argument: $1";;
  esac
done

# --------------------------- Pre-flight --------------------------------------
[[ -f "app/main.py" && -f "alembic.ini" ]] || fail "Run from repo root (missing app/main.py or alembic.ini)"

log "Environment file: ${ENV_FILE:-'(none)'}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  set -a; . "$ENV_FILE"; set +a
  ok "Loaded env file $ENV_FILE"
else
  warn "Env file not found (proceeding)"
fi

# Normalize potential JSON-like CORS vars to avoid pydantic parse issues during config import
if [[ ${CORS_ORIGINS:-} =~ \[ ]]; then export CORS_ORIGINS='[]'; fi
if [[ ${CORS_ALLOW_ORIGINS:-} =~ \[ ]]; then export CORS_ALLOW_ORIGINS='[]'; fi

# ----------------------- Virtual Environment ---------------------------------
if [[ ! -x .venv/bin/python ]]; then
  log "Creating virtual environment (.venv)"
  python3 -m venv .venv || fail "Failed to create venv"
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m ensurepip --upgrade >/dev/null 2>&1 || true
pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
python -c "import alembic" 2>/dev/null || pip install alembic >/dev/null 2>&1

# ----------------------- Determine DB URL ------------------------------------
DB_URL_FROM_ENV=${DB_URL:-}
DB_URL=$(python - <<'PYCODE'
from app.config import settings
print(settings.database_url)
PYCODE
)
log "Resolved database_url=${DB_URL} (env override was: ${DB_URL_FROM_ENV:-'(none)'})"

# ----------------------- SQLite Backup (if applicable) ----------------------
DB_IS_SQLITE=0
SQLITE_PATH=""
if [[ "$DB_URL" == sqlite:///* ]]; then
  DB_IS_SQLITE=1
  SQLITE_PATH="${DB_URL#sqlite:///}"
  if [[ -f "$SQLITE_PATH" && $DO_BACKUP -eq 1 ]]; then
    TS=$(date '+%Y%m%d_%H%M%S')
    BAK="${SQLITE_PATH}.${TS}.bak"
    cp -p "$SQLITE_PATH" "$BAK" || fail "SQLite backup failed"
    ok "SQLite backup created: $BAK"
  fi
fi

# ----------------------- Alembic State Introspection -------------------------
log "Inspecting Alembic state..."
CURRENT_REV=$(alembic current 2>/dev/null | awk '{print $1}' || true)
HEADS_COUNT=$(alembic heads 2>/dev/null | wc -l | tr -d ' ' || echo 0)

if [[ -z "$CURRENT_REV" ]]; then
  warn "No current Alembic revision (either fresh DB or untracked legacy)."
  if [[ $AUTO_BASELINE -eq 1 ]]; then
    log "Auto-baseline requested. Stamping database with head without running migrations yet..."
    if [[ $DRY_RUN -eq 1 ]]; then
      warn "Dry-run: would run: alembic stamp head"
    else
      alembic stamp head || fail "Baseline (stamp head) failed"
    fi
    CURRENT_REV=$(alembic current 2>/dev/null | awk '{print $1}' || true)
  else
    warn "Consider: rerun with --auto-baseline if this DB predates migrations."
  fi
fi

if [[ $HEADS_COUNT -gt 1 ]]; then
  warn "Multiple Alembic heads detected ($HEADS_COUNT). Manual merge required before proceeding."; exit 2
fi

log "Current revision: ${CURRENT_REV:-'(none)'}"
log "Head revision(s):"; alembic heads || true

# ----------------------- Planned Upgrade -------------------------------------
if [[ $DRY_RUN -eq 1 ]]; then
  warn "Dry-run mode: skipping upgrade."
else
  log "Running alembic upgrade head..."
  if ! alembic upgrade head; then
    fail "Alembic upgrade failed"
  fi
  ok "Alembic upgrade complete"
fi

POST_REV=$(alembic current 2>/dev/null | awk '{print $1}' || true)
log "Post-migration revision: ${POST_REV:-'(unknown)'}"

# ----------------------- Post-Migration Column Validation --------------------
MISSING_COLUMNS=()
if [[ $EXPECT_PUSH_COLUMNS -eq 1 ]]; then
  log "Validating push strategy columns..."
  if [[ $DB_IS_SQLITE -eq 1 ]]; then
    HAS_UPDATE=$(sqlite3 "$SQLITE_PATH" "PRAGMA table_info(scenes);" | awk -F'|' '{print $2}' | grep -x 'update_strategy' || true)
    HAS_FALLBACK=$(sqlite3 "$SQLITE_PATH" "PRAGMA table_info(scenes);" | awk -F'|' '{print $2}' | grep -x 'push_fallback_poll_seconds' || true)
  else
    # Generic SQL (Postgres/MySQL) via Python so we don't depend on psql/mysql CLIs
    python - <<'PYCODE' > .db_columns.tmp
from app.config import settings
import re
import sys
import sqlalchemy as sa
engine = sa.create_engine(settings.database_url)
try:
    insp = sa.inspect(engine)
    cols = {c['name'] for c in insp.get_columns('scenes')}
    print('\n'.join(sorted(cols)))
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(0)
PYCODE
    HAS_UPDATE=$(grep -x 'update_strategy' .db_columns.tmp || true)
    HAS_FALLBACK=$(grep -x 'push_fallback_poll_seconds' .db_columns.tmp || true)
    rm -f .db_columns.tmp
  fi
  [[ -z "$HAS_UPDATE" ]] && MISSING_COLUMNS+=(update_strategy)
  [[ -z "$HAS_FALLBACK" ]] && MISSING_COLUMNS+=(push_fallback_poll_seconds)
  if (( ${#MISSING_COLUMNS[@]} > 0 )); then
    warn "Missing expected column(s): ${MISSING_COLUMNS[*]}"
    cat <<'EOM'
Suggested manual SQL patches (choose appropriate dialect):
-- SQLite / PostgreSQL (simple)
ALTER TABLE scenes ADD COLUMN update_strategy VARCHAR(50) NOT NULL DEFAULT 'scheduler';
ALTER TABLE scenes ADD COLUMN push_fallback_poll_seconds INTEGER;
-- Backfill existing rows (if needed) for push_fallback_poll_seconds only when strategy becomes 'push'
-- Example future logic: UPDATE scenes SET push_fallback_poll_seconds=300 WHERE update_strategy='push' AND push_fallback_poll_seconds IS NULL;

If these columns correspond to a migration file that is not in this DB's lineage, create a NEW migration referencing the current head instead of force-applying divergent ones.
EOM
    exit 2
  else
    ok "Push strategy columns present"
  fi
fi

ok "Database migration script finished successfully"
