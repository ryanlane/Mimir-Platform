#!/bin/bash
set -e

# Simple Mimir API File Copy Script
# Copies the refactored Mimir API files to the remote server

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
read -p "Enter remote path [ /opt/mimir/mimir-api]: " REMOTE_PATH
REMOTE_PATH="${REMOTE_PATH:-/opt/mimir/mimir-api/}"

echo
echo "Configuration:"
echo "• Remote Host: $REMOTE_HOST"
echo "• Remote User: $REMOTE_USER"  
echo "• Remote Path: $REMOTE_PATH"
echo

read -p "Continue? [Y/n]: " confirm
if [[ $confirm =~ ^[Nn]$ ]]; then
    echo "Copy cancelled."
    exit 0
fi

# Verify we're in the right directory
if [ ! -f "main.py" ] || [ ! -d "app" ]; then
    error "Please run this script from the api-service directory"
fi

log "� Preparing files for copy..."

# Set up SSH connection multiplexing to avoid multiple password prompts
SSH_CONTROL_PATH="/tmp/ssh_mux_%h_%p_%r"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=$SSH_CONTROL_PATH -o ControlPersist=10m"

# Create remote directory (this will prompt for password once)
ssh $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_PATH"

# Copy files using scp with shared connection
log "📤 Copying files to remote server..."

scp $SSH_OPTS -r app/ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
scp $SSH_OPTS main.py "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
scp $SSH_OPTS requirements.txt "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"

# Copy optional files if they exist
[ -f "pyproject.toml" ] && scp $SSH_OPTS pyproject.toml "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -d "alembic" ] && scp $SSH_OPTS -r alembic/ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -f "alembic.ini" ] && scp $SSH_OPTS alembic.ini "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"

# Copy deployment files if they exist
if [ -d "deploy" ]; then
    scp $SSH_OPTS -r deploy/ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
fi

# Clean up SSH connection
ssh $SSH_OPTS -O exit "$REMOTE_USER@$REMOTE_HOST" 2>/dev/null || true

success "Files copied to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"

echo
echo "Files have been copied to the remote server."
echo "You can now handle the setup and configuration on the remote server."
