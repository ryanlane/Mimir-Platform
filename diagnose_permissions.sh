#!/bin/bash
"""
Diagnose Mimir API Permission Issues

This script checks the current state of file permissions and ownership
to help diagnose API access issues.
"""

echo "🔍 Mimir API Permission Diagnostic"
echo "=================================="

# Check API service status
echo ""
echo "📡 API Service Status:"
if systemctl is-active --quiet mimir-api; then
    echo "   ✅ mimir-api service is running"
    API_PID=$(pgrep -f "mimir-api")
    API_USER=$(ps -o user= -p $API_PID 2>/dev/null)
    if [ -n "$API_USER" ]; then
        echo "   👤 Running as user: $API_USER"
    fi
else
    echo "   ❌ mimir-api service is not running"
fi

# Check base directory
BASE_DIR="/var/opt/mimir/mimir-api/channels"
echo ""
echo "📂 Base Directory: $BASE_DIR"
if [ -d "$BASE_DIR" ]; then
    echo "   ✅ Directory exists"
    ls -ld "$BASE_DIR"
else
    echo "   ❌ Directory does not exist"
    exit 1
fi

# Check photo frame channel specifically
PHOTO_FRAME_DIR="$BASE_DIR/photo_frame"
echo ""
echo "📸 Photo Frame Channel: $PHOTO_FRAME_DIR"
if [ -d "$PHOTO_FRAME_DIR" ]; then
    echo "   ✅ Photo frame directory exists"
    ls -ld "$PHOTO_FRAME_DIR"
    
    # Check uploads directory
    UPLOADS_DIR="$PHOTO_FRAME_DIR/assets/uploads"
    if [ -d "$UPLOADS_DIR" ]; then
        echo ""
        echo "📁 Uploads Directory: $UPLOADS_DIR"
        ls -ld "$UPLOADS_DIR"
        
        echo ""
        echo "📸 Sample Image Files (first 5):"
        ls -la "$UPLOADS_DIR" | head -8
        
        # Count files with permission issues
        UNREADABLE_COUNT=$(find "$UPLOADS_DIR" -type f ! -readable 2>/dev/null | wc -l)
        TOTAL_COUNT=$(find "$UPLOADS_DIR" -type f 2>/dev/null | wc -l)
        
        echo ""
        echo "📊 File Access Summary:"
        echo "   📄 Total files: $TOTAL_COUNT"
        echo "   ❌ Unreadable files: $UNREADABLE_COUNT"
        
        if [ "$UNREADABLE_COUNT" -gt 0 ]; then
            echo "   ⚠️  Permission issues detected!"
            echo ""
            echo "🔧 Files with permission issues:"
            find "$UPLOADS_DIR" -type f ! -readable 2>/dev/null | head -5
        else
            echo "   ✅ All files are readable"
        fi
    else
        echo "   ❌ Uploads directory does not exist"
    fi
    
    # Check data directory
    DATA_DIR="$PHOTO_FRAME_DIR/data"
    if [ -d "$DATA_DIR" ]; then
        echo ""
        echo "💾 Data Directory: $DATA_DIR"
        ls -ld "$DATA_DIR"
        
        if [ -f "$DATA_DIR/galleries.json" ]; then
            echo "   ✅ galleries.json exists"
            ls -la "$DATA_DIR/galleries.json"
        else
            echo "   ❌ galleries.json not found"
        fi
    else
        echo "   ❌ Data directory does not exist"
    fi
    
else
    echo "   ❌ Photo frame directory does not exist"
fi

# Check user/group info
echo ""
echo "👥 User/Group Information:"
echo "   Current user: $(whoami)"
echo "   Current groups: $(groups)"

if getent passwd mimir >/dev/null 2>&1; then
    echo "   ✅ 'mimir' user exists"
    echo "   mimir user info: $(getent passwd mimir)"
else
    echo "   ❌ 'mimir' user does not exist"
fi

if getent group mimir >/dev/null 2>&1; then
    echo "   ✅ 'mimir' group exists"
    echo "   mimir group members: $(getent group mimir)"
else
    echo "   ❌ 'mimir' group does not exist"
fi

# Test API connectivity
echo ""
echo "🌐 API Connectivity Test:"
if curl -s --connect-timeout 5 http://oak:5000/api/channels >/dev/null 2>&1; then
    echo "   ✅ API server is responding"
    
    # Test specific endpoints
    echo "   Testing specific endpoints:"
    
    # Test channels list
    if curl -s --connect-timeout 5 http://oak:5000/api/channels | grep -q "channels"; then
        echo "     ✅ /api/channels - OK"
    else
        echo "     ❌ /api/channels - Failed"
    fi
    
    # Test photo frame image
    if curl -s --connect-timeout 5 -I http://oak:5000/api/channels/photo_frame/current.jpg | grep -q "200 OK"; then
        echo "     ✅ /api/channels/photo_frame/current.jpg - OK"
    else
        echo "     ❌ /api/channels/photo_frame/current.jpg - Failed"
    fi
    
else
    echo "   ❌ API server is not responding"
fi

echo ""
echo "💡 Recommendations:"
echo "==================="

if [ "$UNREADABLE_COUNT" -gt 0 ]; then
    echo "🔧 Fix file permissions:"
    echo "   sudo ./fix_permissions.sh"
fi

if systemctl is-active --quiet mimir-api; then
    if [ -n "$API_USER" ] && [ "$API_USER" != "mimir" ]; then
        echo "👤 Consider running API service as 'mimir' user"
    fi
    echo "🔄 Restart API service after fixing permissions:"
    echo "   sudo systemctl restart mimir-api"
else
    echo "🚀 Start the API service:"
    echo "   sudo systemctl start mimir-api"
fi

echo "🧪 Test API endpoints after fixes:"
echo "   python3 test_all_channel_endpoints.py --host oak --port 5000 --photo-frame-only"
