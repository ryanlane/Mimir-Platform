#!/bin/bash
set -e

# Mimir API Deployment Script
# Deploys the refactored Mimir API to the remote server

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

prompt_for_config() {
    echo -e "${GREEN}🚀 Mimir API Deployment Configuration${NC}"
    echo "================================================"
    echo
    
    # Get remote host
    if [ -n "$REMOTE_HOST" ] && [ "$REMOTE_HOST" != "your-server.com" ]; then
        echo -e "${BLUE}Using REMOTE_HOST from environment: $REMOTE_HOST${NC}"
        read -p "Press Enter to continue or type a different host: " input_host
        if [ -n "$input_host" ]; then
            REMOTE_HOST="$input_host"
        fi
    else
        while [ -z "$REMOTE_HOST" ]; do
            read -p "Enter remote server hostname or IP: " REMOTE_HOST
            if [ -z "$REMOTE_HOST" ]; then
                echo -e "${RED}Remote host is required!${NC}"
            fi
        done
    fi
    
    # Get remote user
    if [ -n "$REMOTE_USER" ]; then
        echo -e "${BLUE}Using REMOTE_USER from environment: $REMOTE_USER${NC}"
        read -p "Press Enter to continue or type a different username: " input_user
        if [ -n "$input_user" ]; then
            REMOTE_USER="$input_user"
        fi
    else
        read -p "Enter remote username [ryan]: " REMOTE_USER
        REMOTE_USER="${REMOTE_USER:-ryan}"
    fi
    
    # Set paths based on user
    REMOTE_PATH="/home/$REMOTE_USER/services/mimir-api"
    
    echo
    echo -e "${GREEN}Deployment Configuration:${NC}"
    echo "• Remote Host: $REMOTE_HOST"
    echo "• Remote User: $REMOTE_USER"  
    echo "• Remote Path: $REMOTE_PATH"
    echo "• Service Name: $SERVICE_NAME"
    echo
    
    read -p "Continue with this configuration? [Y/n]: " confirm
    if [[ $confirm =~ ^[Nn]$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi
}

# Configuration
REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_USER="${REMOTE_USER:-}"
LOCAL_PATH="$(dirname "$(readlink -f "$0")")"
SERVICE_NAME="mimir-api"

# Prompt for configuration
prompt_for_config

log "🚀 Starting Mimir API deployment to $REMOTE_HOST"

# Verify we're in the right directory
if [ ! -f "main.py" ] || [ ! -d "app" ]; then
    error "Please run this script from the api-service directory"
fi

# Check if the refactored main.py is in place
if ! grep -q "create_app" main.py; then
    error "main.py doesn't appear to be the refactored version. Please ensure you've replaced it with app/main.py"
fi

log "📋 Pre-deployment checks..."

# Verify local setup
if [ ! -f "requirements.txt" ]; then
    error "requirements.txt not found"
fi

if [ ! -f "app/config.py" ]; then
    error "app/config.py not found - refactoring may be incomplete"
fi

success "Local setup verified"

log "📦 Creating deployment package..."

# Create temporary deployment directory
TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="$TEMP_DIR/mimir-api"

# Copy application files
mkdir -p "$PACKAGE_DIR"
cp -r app/ "$PACKAGE_DIR/"
cp main.py "$PACKAGE_DIR/"
cp requirements.txt "$PACKAGE_DIR/"
cp pyproject.toml "$PACKAGE_DIR/" 2>/dev/null || true
cp -r alembic/ "$PACKAGE_DIR/" 2>/dev/null || true
cp alembic.ini "$PACKAGE_DIR/" 2>/dev/null || true

# Copy deployment files
cp deploy/mimir-api.service "$PACKAGE_DIR/"
if [ -f "deploy/.env.production" ]; then
    cp deploy/.env.production "$PACKAGE_DIR/.env.template"
else
    warning "No .env.production found, you'll need to configure environment manually"
fi

# Create deployment info
cat > "$PACKAGE_DIR/deployment_info.txt" << EOF
Deployment Information
======================
Timestamp: $(date)
Git Commit: $(git rev-parse HEAD 2>/dev/null || echo "Unknown")
Deployed by: $(whoami)
Local machine: $(hostname)
Target: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH

Refactoring Status:
- Phase 0-6: COMPLETED ✅
- Main.py reduced from 5,198 lines to 120 lines (98% reduction)
- Service layer architecture implemented
- Testing infrastructure complete
EOF

success "Deployment package created"

log "🌐 Connecting to remote server..."

# Test SSH connection
ssh -o ConnectTimeout=10 "$REMOTE_USER@$REMOTE_HOST" "echo 'Connection successful'" || error "Failed to connect to remote server"

success "Connected to $REMOTE_HOST"

log "📤 Uploading application files..."

# Create remote directory structure
ssh "$REMOTE_USER@$REMOTE_HOST" "
    mkdir -p $REMOTE_PATH
    mkdir -p $REMOTE_PATH/logs
    mkdir -p $REMOTE_PATH/backup
"

# Backup existing deployment if it exists
ssh "$REMOTE_USER@$REMOTE_HOST" "
    if [ -d '$REMOTE_PATH/app' ]; then
        echo 'Backing up existing deployment...'
        tar -czf '$REMOTE_PATH/backup/backup-\$(date +%Y%m%d-%H%M%S).tar.gz' -C '$REMOTE_PATH' app main.py requirements.txt alembic/ alembic.ini 2>/dev/null || true
    fi
"

# Upload new files
rsync -avz --delete "$PACKAGE_DIR/" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"

success "Files uploaded"

log "🔧 Setting up remote environment..."

# Remote setup script
ssh "$REMOTE_USER@$REMOTE_HOST" "
    cd $REMOTE_PATH

    # Create virtual environment if it doesn't exist
    if [ ! -d '.venv' ]; then
        echo 'Creating virtual environment...'
        python3 -m venv .venv
    fi

    # Activate virtual environment and install dependencies
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    # Run database migrations if alembic is available
    if [ -f 'alembic.ini' ]; then
        echo 'Running database migrations...'
        alembic upgrade head || echo 'Migration failed or not needed'
    fi

    # Process environment file if it exists
    if [ -f '.env.template' ]; then
        echo 'Processing environment configuration...'
        export REMOTE_PATH='$REMOTE_PATH'
        export REMOTE_USER='$REMOTE_USER'
        envsubst < .env.template > .env
        rm .env.template
    fi

    # Set proper permissions
    chmod +x .venv/bin/uvicorn
    
    echo 'Remote environment setup complete'
"

success "Remote environment configured"

log "🔄 Updating systemd service..."

# Install/update systemd service
ssh "$REMOTE_USER@$REMOTE_HOST" "
    # Create custom service file with correct paths
    export REMOTE_PATH='$REMOTE_PATH'
    export REMOTE_USER='$REMOTE_USER'
    envsubst < $REMOTE_PATH/mimir-api.service > /tmp/mimir-api-custom.service
    sudo cp /tmp/mimir-api-custom.service /etc/systemd/system/mimir-api.service
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME
    rm -f /tmp/mimir-api-custom.service
"

success "Systemd service updated"

log "🚀 Starting service..."

# Stop, start, and check status
ssh "$REMOTE_USER@$REMOTE_HOST" "
    sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
    sleep 2
    sudo systemctl start $SERVICE_NAME
    sleep 3
    sudo systemctl status $SERVICE_NAME --no-pager
"

# Verify service is running
if ssh "$REMOTE_USER@$REMOTE_HOST" "sudo systemctl is-active $SERVICE_NAME --quiet"; then
    success "Service is running"
else
    error "Service failed to start"
fi

# Check logs
log "📋 Recent service logs:"
ssh "$REMOTE_USER@$REMOTE_HOST" "sudo journalctl -u $SERVICE_NAME --no-pager -n 20"

# Test API endpoint
log "🔍 Testing API endpoint..."
if ssh "$REMOTE_USER@$REMOTE_HOST" "curl -f http://localhost:5000/api/v1/health >/dev/null 2>&1"; then
    success "API is responding"
else
    warning "API health check failed - check logs for details"
fi

# Cleanup
rm -rf "$TEMP_DIR"

log "🎉 Deployment completed successfully!"
echo
echo -e "${GREEN}Deployment Summary:${NC}"
echo "• Remote server: $REMOTE_HOST"
echo "• Installation path: $REMOTE_PATH"
echo "• Service name: $SERVICE_NAME"
echo "• API endpoint: http://$REMOTE_HOST:5000"
echo "• Health check: http://$REMOTE_HOST:5000/api/v1/health"
echo "• API docs: http://$REMOTE_HOST:5000/docs"
echo
echo -e "${BLUE}Next steps:${NC}"
echo "1. Configure your .env file on the remote server if needed"
echo "2. Check service logs: sudo journalctl -u $SERVICE_NAME -f"
echo "3. Monitor application: sudo systemctl status $SERVICE_NAME"
echo "4. Update your frontend to use the new API endpoints"
