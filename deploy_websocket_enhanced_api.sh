#!/bin/bash
"""
Deploy WebSocket Enhanced API to Production
Deploys the Redis-integrated API with new WebSocket distribution event broadcasting.
"""

set -e

echo "🚀 Deploying WebSocket Enhanced Mimir API"
echo "=========================================="

# Configuration
REMOTE_HOST="oak"
REMOTE_USER="ryan"  # Adjust if different
REMOTE_PATH="/home/${REMOTE_USER}/code"
API_PATH="${REMOTE_PATH}/mimir-api"
SERVICE_NAME="mimir-api.service"

echo "📡 Connecting to $REMOTE_HOST..."

# 1. Upload enhanced API files
echo "📁 Uploading enhanced API files..."
scp -r api-service/ ${REMOTE_USER}@${REMOTE_HOST}:${API_PATH}/

# 2. Upload test script
echo "📋 Uploading WebSocket test script..."
scp test_websocket_events.py ${REMOTE_USER}@${REMOTE_HOST}:${API_PATH}/

# 3. Update dependencies if needed
echo "📦 Checking dependencies..."
ssh ${REMOTE_USER}@${REMOTE_HOST} << 'EOF'
cd /home/ryan/code/mimir-api
source venv/bin/activate

# Install websockets and requests for testing if not already installed
pip install websockets requests

echo "✅ Dependencies updated"
EOF

# 4. Restart the API service
echo "🔄 Restarting API service..."
ssh ${REMOTE_USER}@${REMOTE_HOST} << EOF
# Stop the service
sudo systemctl stop ${SERVICE_NAME}

# Start the service
sudo systemctl start ${SERVICE_NAME}

# Check status
sleep 3
sudo systemctl status ${SERVICE_NAME} --no-pager

echo "✅ API service restarted"
EOF

# 5. Test API availability
echo "🧪 Testing API availability..."
sleep 5

if curl -f http://oak:5000/api/health > /dev/null 2>&1; then
    echo "✅ API is responding"
    
    # Check Redis integration
    echo "🔍 Testing Redis integration..."
    if curl -f http://oak:5000/api/admin/redis/status > /dev/null 2>&1; then
        echo "✅ Redis integration working"
    else
        echo "⚠️  Redis integration may have issues"
    fi
    
    echo ""
    echo "🎉 WebSocket Enhanced API Deployment Complete!"
    echo ""
    echo "Next steps:"
    echo "1. Run WebSocket event test:"
    echo "   ssh ryan@oak 'cd /home/ryan/code/mimir-api && python test_websocket_events.py'"
    echo ""
    echo "2. Monitor distribution events in browser:"
    echo "   Connect to ws://oak:5000/ws"
    echo ""
    echo "3. Check real-time performance metrics:"
    echo "   Watch for distribution_performance events every 30 seconds"
    echo ""
    echo "4. Test content assignment events:"
    echo "   Use display clients to claim content and watch for events"
    
else
    echo "❌ API deployment may have failed"
    echo "Check service logs: ssh pi@oak 'sudo journalctl -u ${SERVICE_NAME} -f'"
fi
