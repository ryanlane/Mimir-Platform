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
read -p "Enter remote path [/home/$REMOTE_USER/services/mimir-api]: " REMOTE_PATH
REMOTE_PATH="${REMOTE_PATH:-/home/$REMOTE_USER/services/mimir-api}"

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

# Create remote directory
ssh "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_PATH"

# Copy files using scp
log "📤 Copying files to remote server..."

scp -r app/ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
scp main.py "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
scp requirements.txt "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"

# Copy optional files if they exist
[ -f "pyproject.toml" ] && scp pyproject.toml "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -d "alembic" ] && scp -r alembic/ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
[ -f "alembic.ini" ] && scp alembic.ini "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"

# Copy deployment files if they exist
if [ -d "deploy" ]; then
    scp -r deploy/ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"
fi

success "Files copied to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"

echo
echo "Files have been copied to the remote server."
echo "You can now handle the setup and configuration on the remote server."
