#!/bin/bash
# Server management script for remote deployment

set -e

# Get current user and set service path
CURRENT_USER=$(whoami)
SERVICE_NAME="mimir-api"
SERVICE_PATH="/home/$CURRENT_USER/services/mimir-api"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

case "$1" in
    "status")
        log "📊 Checking Mimir API service status..."
        systemctl status $SERVICE_NAME --no-pager
        echo
        if systemctl is-active $SERVICE_NAME --quiet; then
            success "Service is running"
        else
            error "Service is not running"
        fi
        ;;
    "start")
        log "🚀 Starting Mimir API service..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        if systemctl is-active $SERVICE_NAME --quiet; then
            success "Service started successfully"
        else
            error "Failed to start service"
            systemctl status $SERVICE_NAME --no-pager
        fi
        ;;
    "stop")
        log "🛑 Stopping Mimir API service..."
        sudo systemctl stop $SERVICE_NAME
        sleep 1
        if ! systemctl is-active $SERVICE_NAME --quiet; then
            success "Service stopped successfully"
        else
            error "Failed to stop service"
        fi
        ;;
    "restart")
        log "🔄 Restarting Mimir API service..."
        sudo systemctl restart $SERVICE_NAME
        sleep 3
        if systemctl is-active $SERVICE_NAME --quiet; then
            success "Service restarted successfully"
        else
            error "Failed to restart service"
            systemctl status $SERVICE_NAME --no-pager
        fi
        ;;
    "logs")
        log "📋 Showing recent service logs..."
        sudo journalctl -u $SERVICE_NAME --no-pager -n 50
        ;;
    "logs-follow"|"tail")
        log "📋 Following service logs (Ctrl+C to exit)..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    "logs-errors")
        log "🚨 Showing error logs..."
        sudo journalctl -u $SERVICE_NAME --no-pager -p err
        ;;
    "health")
        log "🔍 Checking API health..."
        if curl -f -s http://localhost:5000/api/v1/health > /dev/null; then
            success "API is responding"
            echo "Health endpoint: $(curl -s http://localhost:5000/api/v1/health)"
        else
            error "API is not responding"
            warning "Check service logs: $0 logs"
        fi
        ;;
    "reload")
        log "🔄 Reloading systemd and restarting service..."
        sudo systemctl daemon-reload
        sudo systemctl restart $SERVICE_NAME
        sleep 3
        if systemctl is-active $SERVICE_NAME --quiet; then
            success "Service reloaded and restarted successfully"
        else
            error "Failed to reload service"
        fi
        ;;
    "enable")
        log "🔧 Enabling service to start on boot..."
        sudo systemctl enable $SERVICE_NAME
        success "Service enabled"
        ;;
    "disable")
        log "🔧 Disabling service from starting on boot..."
        sudo systemctl disable $SERVICE_NAME
        success "Service disabled"
        ;;
    "update")
        log "📦 Updating application..."
        cd $SERVICE_PATH
        
        # Create backup
        backup_file="backup-$(date +%Y%m%d-%H%M%S).tar.gz"
        tar -czf "backup/$backup_file" app/ main.py requirements.txt alembic/ 2>/dev/null || true
        log "Created backup: $backup_file"
        
        # Pull latest code (if git repo)
        if [ -d ".git" ]; then
            git pull
        else
            warning "Not a git repository - manual update required"
        fi
        
        # Update dependencies
        source .venv/bin/activate
        pip install -r requirements.txt
        
        # Run migrations
        if [ -f "alembic.ini" ]; then
            alembic upgrade head
        fi
        
        # Restart service
        sudo systemctl restart $SERVICE_NAME
        
        success "Application updated"
        ;;
    "backup")
        log "💾 Creating application backup..."
        cd $SERVICE_PATH
        backup_file="backup/manual-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
        mkdir -p backup
        tar -czf "$backup_file" app/ main.py requirements.txt alembic/ .env logs/ app.db 2>/dev/null || true
        success "Backup created: $backup_file"
        ;;
    "restore")
        if [ -z "$2" ]; then
            echo "Available backups:"
            ls -la backup/ 2>/dev/null || echo "No backups found"
            echo
            echo "Usage: $0 restore <backup-file>"
            exit 1
        fi
        
        log "🔄 Restoring from backup: $2"
        cd $SERVICE_PATH
        
        if [ ! -f "backup/$2" ]; then
            error "Backup file not found: backup/$2"
            exit 1
        fi
        
        # Stop service
        sudo systemctl stop $SERVICE_NAME
        
        # Restore files
        tar -xzf "backup/$2"
        
        # Restart service
        sudo systemctl start $SERVICE_NAME
        
        success "Restored from backup: $2"
        ;;
    "config")
        log "⚙️ Application configuration:"
        echo "Service file: /etc/systemd/system/$SERVICE_NAME.service"
        echo "Working directory: $SERVICE_PATH"
        echo "Environment file: $SERVICE_PATH/.env"
        echo "Log location: journalctl -u $SERVICE_NAME"
        echo "Database: $SERVICE_PATH/app.db"
        echo
        if [ -f "$SERVICE_PATH/.env" ]; then
            echo "Environment variables:"
            grep -v "^#" "$SERVICE_PATH/.env" | grep -v "^$" || true
        else
            warning "No .env file found"
        fi
        ;;
    "debug")
        log "🐛 Debug information:"
        echo "Service status:"
        systemctl status $SERVICE_NAME --no-pager || true
        echo
        echo "Recent logs:"
        sudo journalctl -u $SERVICE_NAME --no-pager -n 10 || true
        echo
        echo "Process information:"
        ps aux | grep -E "(uvicorn|python.*main)" | grep -v grep || echo "No processes found"
        echo
        echo "Port usage:"
        netstat -tlnp | grep :5000 || echo "Port 5000 not in use"
        echo
        echo "Disk space:"
        df -h $SERVICE_PATH
        ;;
    "help"|"-h"|"--help")
        echo -e "${GREEN}Mimir API Server Management Script${NC}"
        echo
        echo "Usage: $0 <command> [options]"
        echo
        echo "Service Commands:"
        echo "  status         Show service status"
        echo "  start          Start the service"
        echo "  stop           Stop the service"
        echo "  restart        Restart the service"
        echo "  reload         Reload systemd and restart"
        echo "  enable         Enable service on boot"
        echo "  disable        Disable service on boot"
        echo
        echo "Monitoring Commands:"
        echo "  logs           Show recent logs"
        echo "  logs-follow    Follow logs in real-time"
        echo "  logs-errors    Show error logs only"
        echo "  health         Check API health"
        echo "  debug          Show debug information"
        echo
        echo "Maintenance Commands:"
        echo "  update         Update application code"
        echo "  backup         Create manual backup"
        echo "  restore <file> Restore from backup"
        echo "  config         Show configuration"
        echo
        echo "Examples:"
        echo "  $0 status      # Check if service is running"
        echo "  $0 logs-follow # Watch logs in real-time"
        echo "  $0 restart     # Restart the service"
        echo "  $0 backup      # Create backup"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run '$0 help' for available commands"
        exit 1
        ;;
esac
