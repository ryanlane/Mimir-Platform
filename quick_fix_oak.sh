#!/bin/bash
# Quick Permission Fix for Mimir API
# Run this script on the oak server to fix file permissions

echo "🔧 Quick Mimir Permission Fix"
echo "============================="

# Check if running on the correct server
if [ "$(hostname)" != "oak" ]; then
    echo "⚠️  Warning: This should be run on the 'oak' server"
    echo "   Current hostname: $(hostname)"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

BASE_DIR="/var/opt/mimir/mimir-api/channels"

if [ ! -d "$BASE_DIR" ]; then
    echo "❌ Directory $BASE_DIR not found"
    echo "💡 Make sure you're running this on the oak server"
    exit 1
fi

echo "📂 Found base directory: $BASE_DIR"

# Check current user and suggest sudo if needed
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Running as non-root user: $(whoami)"
    echo "💡 For ownership changes, run with: sudo $0"
    echo ""
fi

# Fix photo frame channel permissions specifically
PHOTO_FRAME_DIR="$BASE_DIR/photo_frame"
if [ -d "$PHOTO_FRAME_DIR" ]; then
    echo "📸 Fixing photo frame channel permissions..."
    
    # Make all directories readable/executable
    echo "   📁 Setting directory permissions (755)..."
    find "$PHOTO_FRAME_DIR" -type d -exec chmod 755 {} \; 2>/dev/null
    
    # Make all files readable
    echo "   📄 Setting file permissions (644)..."
    find "$PHOTO_FRAME_DIR" -type f -exec chmod 644 {} \; 2>/dev/null
    
    # Set ownership if running as root
    if [ "$EUID" -eq 0 ]; then
        echo "   👥 Setting ownership to mimir:mimir..."
        chown -R mimir:mimir "$PHOTO_FRAME_DIR" 2>/dev/null
    fi
    
    # Count files affected
    UPLOAD_COUNT=$(find "$PHOTO_FRAME_DIR/assets/uploads" -type f 2>/dev/null | wc -l)
    echo "   ✅ Fixed permissions for $UPLOAD_COUNT files in uploads/"
    
else
    echo "❌ Photo frame directory not found: $PHOTO_FRAME_DIR"
    exit 1
fi

# Check API service
echo ""
echo "🔍 Checking API service..."
if systemctl is-active --quiet mimir-api; then
    API_USER=$(ps -o user= -p $(pgrep -f "mimir-api") 2>/dev/null)
    echo "   ✅ mimir-api service is running as: $API_USER"
    
    echo "   🔄 Restarting service to pick up permission changes..."
    if [ "$EUID" -eq 0 ]; then
        systemctl restart mimir-api
        echo "   ✅ Service restarted"
    else
        echo "   ⚠️  Run 'sudo systemctl restart mimir-api' to restart service"
    fi
else
    echo "   ❌ mimir-api service is not running"
    echo "   💡 Start with: sudo systemctl start mimir-api"
fi

echo ""
echo "🎉 Quick fix complete!"
echo ""
echo "🧪 Test the API now:"
echo "   # From your development machine:"
echo "   python3 test_all_channel_endpoints.py --host oak --port 5000 --photo-frame-only"
