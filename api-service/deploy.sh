#!/bin/bash
set -e

eval "$(ssh-agent -s)"
ssh-add -t 8h ~/.ssh/id_ed25519

# Mimir API Deploy Script (rsync without remote sudo; group-writable tree)
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
log(){ echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
ok(){ echo -e "${GREEN}✅ $1${NC}"; }
fail(){ echo -e "${RED}❌ $1${NC}"; exit 1; }

read -e -r -p "Enter remote server hostname or IP: " -i "oak" REMOTE_HOST
read -e -r -p "Enter remote username: "            -i "$USER" REMOTE_USER
read -e -r -p "Enter remote path: "                -i "/opt/mimir/mimir-api" REMOTE_PATH

echo -e "\nConfig:\n• Host: $REMOTE_HOST\n• User: $REMOTE_USER\n• Path: $REMOTE_PATH\n"
read -p "Continue? [Y/n]: " confirm; [[ $confirm =~ ^[Nn]$ ]] && { echo "Cancelled."; exit 0; }

# sanity: run from repo root
[[ -f "main.py" && -d "app" ]] || fail "Run from the api repo root (needs main.py and app/)"

log "🔐 Checking remote group membership and target path…"
SSH_CTRL="/tmp/ssh_mux_%h_%p_%r"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=$SSH_CTRL -o ControlPersist=10m"
RSYNC_SSH="ssh $SSH_OPTS"

# Check remote user is in 'mimir' group
if ! ssh $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "id -nG | grep -qw mimir"; then
  fail "Remote user '$REMOTE_USER' is not in group 'mimir'. On remote: sudo usermod -aG mimir $REMOTE_USER; then log out/in."
fi

# Create target dir only if missing (this is the only sudo here)
ssh $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "bash -lc '
  if [ ! -d \"$REMOTE_PATH\" ]; then
    echo \"Creating $REMOTE_PATH as mimir:mimir (2775)…\"
    sudo install -d -m 2775 -o mimir -g mimir \"$REMOTE_PATH\"
  fi
  # ensure directory keeps group on new files
  chmod 2775 \"$REMOTE_PATH\" 2>/dev/null || true
'"

log "📦 Preparing files for copy…"

# rsync WITHOUT remote sudo; rely on setgid dir + your membership in 'mimir'
# ensure new dirs/files are group-writable and dirs keep setgid
EXCLUDES=(--exclude='__pycache__/' --exclude='.git/' --exclude='.venv/')
CHMOD="--chmod=Dg+s,Du=rwx,Dg=rwx,Do=rx,Fu=rw,Fg=rw,Fo=r"
RSYNC_BASE=(rsync -a --delete -e "$RSYNC_SSH" "${EXCLUDES[@]}" $CHMOD)

log "📤 Syncing files to $REMOTE_HOST…"
"${RSYNC_BASE[@]}" app/                "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/app/"
"${RSYNC_BASE[@]}" main.py             "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -f requirements.txt ] && "${RSYNC_BASE[@]}" requirements.txt "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -f pyproject.toml ]   && "${RSYNC_BASE[@]}" pyproject.toml   "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -d alembic ]          && "${RSYNC_BASE[@]}" alembic/         "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/alembic/"
[ -f alembic.ini ]      && "${RSYNC_BASE[@]}" alembic.ini      "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -d deploy ]           && "${RSYNC_BASE[@]}" deploy/          "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/deploy/"

echo
read -p "Install requirements and restart mimir-api on remote now? [y/N]: " do_restart
if [[ $do_restart =~ ^[Yy]$ ]]; then
  log "🧰 Ensuring python3-venv, creating venv as mimir, installing deps, and restarting… (you may be prompted for sudo)"

  # 1) Make sure python3-venv exists (so venv can include pip)
  ssh -t $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "sudo bash -lc '
    set -e
    if ! python3 -c \"import venv\" >/dev/null 2>&1; then
      apt-get update
      apt-get install -y python3-venv
    fi
  '"

  # 2) Build/repair venv **as the service user** and install deps
  ssh -t $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "sudo -u mimir bash -lc '
    set -e
    cd \"$REMOTE_PATH\"
    [ -x .venv/bin/python ] || python3 -m venv .venv
    # Ensure pip exists inside the venv, then upgrade toolchain
    .venv/bin/python -m ensurepip --upgrade || true
    .venv/bin/python -m pip -V
    .venv/bin/python -m pip install --upgrade pip setuptools wheel
    [ -f requirements.txt ] && .venv/bin/python -m pip install -r requirements.txt || true
  '"

  # 3) Restart the service
  ssh -t $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "sudo bash -lc '
    systemctl daemon-reload
    systemctl restart mimir-api
    systemctl --no-pager status mimir-api || true
  '"
fi

# close ssh master
ssh $SSH_OPTS -O exit "$REMOTE_USER@$REMOTE_HOST" 2>/dev/null || true
ok "Deploy complete to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"
