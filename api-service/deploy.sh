#!/bin/bash
set -e

# Simple Mimir API Deploy Script (rsync + proper ownership)
# Copies the Mimir API files to the remote server and (optionally) installs deps + restarts the service.

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# Get configuration
read -p "Enter remote server hostname or IP: " REMOTE_HOST
read -p "Enter remote username: " REMOTE_USER
read -p "Enter remote path [/opt/mimir/mimir-api]: " REMOTE_PATH
REMOTE_PATH="${REMOTE_PATH:-/opt/mimir/mimir-api}"

echo
echo "Configuration:"
echo "• Remote Host: $REMOTE_HOST"
echo "• Remote User: $REMOTE_USER"
echo "• Remote Path: $REMOTE_PATH"
echo

read -p "Continue? [Y/n]: " confirm
if [[ $confirm =~ ^[Nn]$ ]]; then
    echo "Deploy cancelled."
    exit 0
fi

# Verify we're in the right directory
if [ ! -f "main.py" ] || [ ! -d "app" ]; then
    error "Please run this script from the api-service repository root (must have main.py and app/)"
fi

log "📦 Preparing files for copy..."

# SSH connection multiplexing to avoid repeated password prompts
SSH_CONTROL_PATH="/tmp/ssh_mux_%h_%p_%r"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=$SSH_CONTROL_PATH -o ControlPersist=10m"

# Ensure target dir exists and is owned by service user/group
ssh $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" \
  "sudo install -d -m 2775 -o mimir -g mimir '$REMOTE_PATH'"

# Common rsync options
EXCLUDES=(--exclude='__pycache__/' --exclude='.git/' --exclude='.venv/')
RSYNC_BASE=(rsync -a --delete --rsync-path='sudo rsync' --chown=mimir:mimir "${EXCLUDES[@]}")

log "📤 Syncing files to remote server..."
# App package
"${RSYNC_BASE[@]}" app/        "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/app/"
# Top-level files
"${RSYNC_BASE[@]}" main.py     "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -f requirements.txt ] && "${RSYNC_BASE[@]}" requirements.txt "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
# Optional files
[ -f pyproject.toml ] && "${RSYNC_BASE[@]}" pyproject.toml     "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -d alembic ]        && "${RSYNC_BASE[@]}" alembic/           "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/alembic/"
[ -f alembic.ini ]    && "${RSYNC_BASE[@]}" alembic.ini        "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
# Optional deploy/ helpers
[ -d deploy ]         && "${RSYNC_BASE[@]}" deploy/            "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/deploy/"

# Optionally install requirements and restart the service
echo
read -p "Install requirements and restart mimir-api on remote now? [y/N]: " do_restart
if [[ $do_restart =~ ^[Yy]$ ]]; then
  log "🧰 Installing Python deps (remote) and restarting service..."
  ssh $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "sudo -u mimir bash -lc '
    set -e
    cd \"$REMOTE_PATH\"
    if [ ! -x .venv/bin/python ]; then
      python3 -m venv .venv
    fi
    .venv/bin/python -m pip install --upgrade pip setuptools wheel
    [ -f requirements.txt ] && .venv/bin/python -m pip install -r requirements.txt || true
  ' && sudo systemctl daemon-reload && sudo systemctl restart mimir-api && sudo systemctl --no-pager status mimir-api"
fi

# Clean up SSH master connection
ssh $SSH_OPTS -O exit "$REMOTE_USER@$REMOTE_HOST" 2>/dev/null || true

success "Deploy complete to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"
