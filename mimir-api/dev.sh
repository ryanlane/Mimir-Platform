#!/bin/bash
# Local development server management script

set -e

# Configuration
APP_MODULE="app.main:app"
HOST="0.0.0.0"
PORT="8000"
WORKERS="1"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

case "$1" in
    "start"|"dev"|"")
        log "🚀 Starting Mimir API development server..."
        echo -e "${YELLOW}API will be available at: http://localhost:$PORT${NC}"
        echo -e "${YELLOW}API docs: http://localhost:$PORT/docs${NC}"
        echo -e "${YELLOW}Health check: http://localhost:$PORT/api/v1/health${NC}"
        echo
        export DEBUG=true
        export LOG_LEVEL=debug
        uvicorn $APP_MODULE --host $HOST --port $PORT --reload --log-level debug --access-log
        ;;
    "prod")
        log "🏭 Starting Mimir API in production mode..."
        uvicorn $APP_MODULE --host $HOST --port $PORT --workers $WORKERS
        ;;
    "test")
        log "🧪 Running tests..."
        python run_tests.py --all
        ;;
    "test-unit")
        log "🧪 Running unit tests..."
        python run_tests.py --unit
        ;;
    "test-integration")
        log "🧪 Running integration tests..."
        python run_tests.py --integration
        ;;
    "coverage")
        log "📊 Running tests with coverage..."
        python run_tests.py --all --coverage
        ;;
    "lint")
        log "🔍 Running linters..."
        ruff check app/
        black --check app/
        mypy app/
        ;;
    "format")
        log "✨ Formatting code..."
        ruff check --fix app/
        black app/
        isort app/
        ;;
    "migrate")
        log "🗃️ Running database migrations..."
        alembic upgrade head
        ;;
    "migration")
        if [ -z "$2" ]; then
            echo "Usage: $0 migration <description>"
            exit 1
        fi
        log "📝 Creating new migration: $2"
        alembic revision --autogenerate -m "$2"
        ;;
    "install")
        log "📦 Installing dependencies..."
        pip install -r requirements.txt
        if [ -f "requirements-test.txt" ]; then
            pip install -r requirements-test.txt
        fi
        ;;
    "clean")
        log "🧹 Cleaning up..."
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        rm -rf .pytest_cache htmlcov .coverage 2>/dev/null || true
        ;;
    "status")
        log "📊 Application status..."
        echo "Current directory: $(pwd)"
        echo "Python version: $(python --version)"
        echo "Virtual environment: ${VIRTUAL_ENV:-Not activated}"
        echo "App module: $APP_MODULE"
        echo "Host: $HOST:$PORT"
        if [ -f "app.db" ]; then
            echo "Database: app.db ($(du -h app.db | cut -f1))"
        fi
        ;;
    "help"|"-h"|"--help")
        echo -e "${GREEN}Mimir API Development Server Management${NC}"
        echo
        echo "Usage: $0 <command>"
        echo
        echo "Commands:"
        echo "  start, dev     Start development server with hot reload"
        echo "  prod           Start production server"
        echo "  test           Run all tests"
        echo "  test-unit      Run unit tests only"
        echo "  test-integration Run integration tests only"
        echo "  coverage       Run tests with coverage report"
        echo "  lint           Run linters (ruff, black, mypy)"
        echo "  format         Format code with black and isort"
        echo "  migrate        Run database migrations"
        echo "  migration <msg> Create new migration"
        echo "  install        Install dependencies"
        echo "  clean          Clean cache and temp files"
        echo "  status         Show application status"
        echo "  help           Show this help message"
        echo
        echo "Examples:"
        echo "  $0 start       # Start development server"
        echo "  $0 test        # Run all tests"
        echo "  $0 format      # Format code"
        echo "  $0 migration 'Add new field'"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run '$0 help' for available commands"
        exit 1
        ;;
esac
