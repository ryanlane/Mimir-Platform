#!/bin/bash
# Enhanced Mimir Update Script with Redis Support

# --- Configuration ---
REPO="/home/ryan/code/mimir-api"

echo "=== Updating Mimir Platform ==="

# --- Update & build first ---
echo "Updating repo: ${REPO} ..."
git -C "${REPO}" fetch
git -C "${REPO}" pull

# --- Start Redis (if not running) ---
echo "Ensuring Redis is running..."
cd "${REPO}"

# Check if Redis container exists and start if needed
if ! sudo docker ps | grep -q mimir-redis; then
    echo "Starting Redis container..."
    sudo docker-compose up -d redis
else
    echo "Redis already running"
fi

# Wait a moment for Redis to be ready
sleep 2

# Verify Redis is healthy
if sudo docker ps | grep mimir-redis | grep -q "healthy"; then
    echo "✅ Redis is healthy"
else
    echo "⚠️  Redis may not be ready yet"
fi

# --- Restart API service ---
echo "Restarting mimir-api service..."
sudo systemctl restart mimir-api

# Wait a moment for service to start
sleep 3

# --- Show logs ---
echo "=== Mimir API Logs ==="
sudo journalctl -u mimir-api -n 100 -f --no-pager
