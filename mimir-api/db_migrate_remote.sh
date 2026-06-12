#!/bin/bash
# Remote Database Migration Orchestrator for Mimir API
# -----------------------------------------------------------------------------
# Run from your DEV machine. No need for a full repo checkout on the remote.
# It will:
#   1. Rsync (minimal) alembic + app/config needed for migrations to a temp dir (optional)
#   2. Ensure a venv exists remotely (under target path) and alembic is installed
#   3. Source remote env file (if present) for DB_URL, etc.
#   4. (Optional) Backup SQLite database before migrating
#   5. Run alembic introspection, (optionally) baseline, then upgrade head
#   6. Validate presence of push columns if requested
#   7. Output a concise summary & exit with code >0 on drift/issue
# -----------------------------------------------------------------------------
# Usage:
#   ./api-service/db_migrate_remote.sh \
#       --host oak --user mimir \
#       --path /opt/mimir/mimir-api \
#       --expect-push-columns
#
# Flags:
#   --host <h>                Remote host (required)
#   --user <u>                Remote SSH user (default: $USER)
#   --path <p>                Remote base path containing app/ & alembic.ini (default: /opt/mimir/mimir-api)
#   --env-file <f>            Remote env file (default: /etc/mimir/mimir-api.env)
#   --no-backup               Skip SQLite backup
#   --dry-run                 Show what would happen (no upgrade)
#   --auto-baseline           Stamp head if no revision present
#   --expect-push-columns     Enforce push-related columns exist post-migration
#   --sync                    Rsync local alembic/ + app/config to remote before running
#   --ssh-opts "..."          Extra SSH options
#   --help                    Show help
# -----------------------------------------------------------------------------
set -euo pipefail
IFS=$'\n\t'

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log(){ echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"; }
ok(){ echo -e "${GREEN}✅ $*${NC}"; }
warn(){ echo -e "${YELLOW}⚠️  $*${NC}"; }
fail(){ echo -e "${RED}❌ $*${NC}"; exit 1; }

REMOTE_HOST=""
REMOTE_USER="${USER:-mimir}"
REMOTE_PATH="/opt/mimir/mimir-api"
REMOTE_ENV_FILE="/etc/mimir/mimir-api.env"
DO_BACKUP=1
DRY_RUN=0
AUTO_BASELINE=0
EXPECT_PUSH_COLUMNS=0
DO_SYNC=0
EXTRA_SSH_OPTS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) REMOTE_HOST="$2"; shift 2;;
    --user) REMOTE_USER="$2"; shift 2;;
    --path) REMOTE_PATH="$2"; shift 2;;
    --env-file) REMOTE_ENV_FILE="$2"; shift 2;;
    --no-backup) DO_BACKUP=0; shift;;
    --dry-run) DRY_RUN=1; shift;;
    --auto-baseline) AUTO_BASELINE=1; shift;;
    --expect-push-columns) EXPECT_PUSH_COLUMNS=1; shift;;
    --sync) DO_SYNC=1; shift;;
    --ssh-opts) EXTRA_SSH_OPTS="$2"; shift 2;;
    --help|-h)
      grep '^# ' "$0" | sed 's/^# //' ; exit 0;;
    *) fail "Unknown arg: $1";;
  esac
done

[[ -n "$REMOTE_HOST" ]] || fail "--host is required"

# ---------------- SSH / rsync availability checks ---------------------------
# Resolve an ssh binary (Linux or Windows OpenSSH) and fail fast if missing.
if command -v ssh >/dev/null 2>&1; then
  SSH_BIN="$(command -v ssh)"
elif [ -x /mnt/c/Windows/System32/OpenSSH/ssh.exe ]; then
  SSH_BIN="/mnt/c/Windows/System32/OpenSSH/ssh.exe"
else
  fail "ssh not found on PATH. Install with: sudo apt-get install -y openssh-client (WSL)"
fi

if [[ $DO_SYNC -eq 1 ]]; then
  if ! command -v rsync >/dev/null 2>&1; then
    fail "rsync not found but --sync requested. Install with: sudo apt-get install -y rsync"
  fi
fi

SSH_CMD="$SSH_BIN $EXTRA_SSH_OPTS"
RSYNC_BASE=(rsync -a -e "$SSH_BIN $EXTRA_SSH_OPTS")

if [[ $DO_SYNC -eq 1 ]]; then
  log "Syncing minimal migration context to remote..."
  # We only need alembic/, alembic.ini, and app/config (settings) + any models referencing metadata.
  # Sending full app/ is safer for model imports; can refine later.
  "${RSYNC_BASE[@]}" --delete alembic/   "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/alembic/"
  "${RSYNC_BASE[@]}" alembic.ini         "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/alembic.ini"
  "${RSYNC_BASE[@]}" app/                "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/app/"
  ok "Sync complete"
else
  log "--sync not provided; assuming remote already has current code"
fi

REMOTE_CMD=$(cat <<'RCMD'
set -euo pipefail
BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log(){ echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"; }
ok(){ echo -e "${GREEN}✅ $*${NC}"; }
warn(){ echo -e "${YELLOW}⚠️  $*${NC}"; }
fail(){ echo -e "${RED}❌ $*${NC}"; exit 1; }

cd "__REMOTE_PATH__" || fail "Remote path missing"
log "At remote path: $(pwd)"
if [[ ! -f alembic.ini ]]; then fail "alembic.ini missing"; fi
if [[ ! -d app ]]; then fail "app/ missing"; fi

if [[ -f "__REMOTE_ENV_FILE__" ]]; then
  set -a; . "__REMOTE_ENV_FILE__"; set +a; log "Loaded env file __REMOTE_ENV_FILE__";
else
  warn "Env file __REMOTE_ENV_FILE__ not found"
fi

# Normalize JSON-like CORS env
if [[ ${CORS_ORIGINS:-} =~ \[ ]]; then export CORS_ORIGINS='[]'; fi
if [[ ${CORS_ALLOW_ORIGINS:-} =~ \[ ]]; then export CORS_ALLOW_ORIGINS='[]'; fi

if [[ ! -x .venv/bin/python ]]; then
  log "Creating venv"; python3 -m venv .venv || fail "venv create failed";
fi
. .venv/bin/activate
python -m ensurepip --upgrade >/dev/null 2>&1 || true
pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
python -c 'import alembic' 2>/dev/null || pip install alembic >/dev/null 2>&1

DB_URL=$(python - <<'PY'
from app.config import settings
print(settings.database_url)
PY
)
log "database_url=$DB_URL"
DB_IS_SQLITE=0; SQLITE_PATH=""
if [[ "$DB_URL" == sqlite:///* ]]; then DB_IS_SQLITE=1; SQLITE_PATH="${DB_URL#sqlite:///}"; fi
if [[ $DB_IS_SQLITE -eq 1 && -f "$SQLITE_PATH" && __DO_BACKUP__ -eq 1 ]]; then
  TS=$(date '+%Y%m%d_%H%M%S'); BAK="$SQLITE_PATH.$TS.bak"; cp -p "$SQLITE_PATH" "$BAK" && ok "SQLite backup: $BAK" || warn "Backup failed";
fi

CURRENT_REV=$(alembic current 2>/dev/null | awk '{print $1}' || true)
HEADS_COUNT=$(alembic heads 2>/dev/null | wc -l | tr -d ' ' || echo 0)
if [[ -z "$CURRENT_REV" ]]; then
  warn "No current revision"
  if [[ __AUTO_BASELINE__ -eq 1 ]]; then
    log "Auto-baseline: stamping head"
    if [[ __DRY_RUN__ -eq 1 ]]; then
      warn "Dry-run: would run alembic stamp head"
    else
      alembic stamp head || fail "stamp failed"
    fi
    CURRENT_REV=$(alembic current 2>/dev/null | awk '{print $1}' || true)
  fi
fi
if [[ $HEADS_COUNT -gt 1 ]]; then warn "Multiple heads ($HEADS_COUNT)"; exit 2; fi
log "Current: ${CURRENT_REV:-'(none)'}"; log "Head(s):"; alembic heads || true

if [[ __DRY_RUN__ -eq 1 ]]; then
  warn "Dry-run: skipping upgrade"
else
  log "Running alembic upgrade head"
  alembic upgrade head || fail "upgrade failed"
  ok "Upgrade complete"
fi
POST_REV=$(alembic current 2>/dev/null | awk '{print $1}' || true)
log "Post revision: ${POST_REV:-'(unknown)'}"

if [[ __EXPECT_PUSH_COLUMNS__ -eq 1 ]]; then
  log "Validating push columns"
  MISSING=()
  if [[ $DB_IS_SQLITE -eq 1 ]]; then
    HAS_U=$(sqlite3 "$SQLITE_PATH" "PRAGMA table_info(scenes);" | awk -F'|' '{print $2}' | grep -x update_strategy || true)
    HAS_F=$(sqlite3 "$SQLITE_PATH" "PRAGMA table_info(scenes);" | awk -F'|' '{print $2}' | grep -x push_fallback_poll_seconds || true)
  else
    python - <<'PY2' > .cols.tmp
from app.config import settings
import sqlalchemy as sa
engine = sa.create_engine(settings.database_url)
try:
    insp = sa.inspect(engine)
    for c in insp.get_columns('scenes'):
        print(c['name'])
except Exception as e:
    print('ERROR', e)
PY2
    HAS_U=$(grep -x update_strategy .cols.tmp || true)
    HAS_F=$(grep -x push_fallback_poll_seconds .cols.tmp || true)
    rm -f .cols.tmp
  fi
  [[ -z "$HAS_U" ]] && MISSING+=(update_strategy)
  [[ -z "$HAS_F" ]] && MISSING+=(push_fallback_poll_seconds)
  if (( ${#MISSING[@]} > 0 )); then
    warn "Missing columns: ${MISSING[*]}"
    cat <<'EOM'
Manual SQL suggestion (SQLite/Postgres):
ALTER TABLE scenes ADD COLUMN update_strategy VARCHAR(50) NOT NULL DEFAULT 'scheduler';
ALTER TABLE scenes ADD COLUMN push_fallback_poll_seconds INTEGER;
EOM
    exit 2
  else
    ok "Push columns present"
  fi
fi
ok "Remote migration completed"
RCMD
)

# Substitute markers
REMOTE_CMD=${REMOTE_CMD//__REMOTE_PATH__/$REMOTE_PATH}
REMOTE_CMD=${REMOTE_CMD//__REMOTE_ENV_FILE__/$REMOTE_ENV_FILE}
REMOTE_CMD=${REMOTE_CMD//__DO_BACKUP__/$DO_BACKUP}
REMOTE_CMD=${REMOTE_CMD//__AUTO_BASELINE__/$AUTO_BASELINE}
REMOTE_CMD=${REMOTE_CMD//__DRY_RUN__/$DRY_RUN}
REMOTE_CMD=${REMOTE_CMD//__EXPECT_PUSH_COLUMNS__/$EXPECT_PUSH_COLUMNS}

log "Executing remote migration on $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH (ssh bin: $SSH_BIN)"
if ! echo "$REMOTE_CMD" | $SSH_CMD "$REMOTE_USER@$REMOTE_HOST" 'bash -s'; then
  fail "Remote migration failed"
fi
ok "Remote migration script finished"
