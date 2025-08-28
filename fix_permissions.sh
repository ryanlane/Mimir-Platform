#!/bin/bash
"""
Fix Mimir Channel File Permissions

This script fixes file permission issues in the Mimir channel directories
to ensure the API service can read all files properly.
"""

echo "🔧 Fixing Mimir Channel File Permissions"
echo "========================================"

# Base directory
BASE_DIR="/var/opt/mimir/mimir-api/channels"

if [ ! -d "$BASE_DIR" ]; then
    echo "❌ Base directory $BASE_DIR does not exist"
    exit 1
fi

echo "📂 Base directory: $BASE_DIR"

# Check current user
CURRENT_USER=$(whoami)
echo "👤 Running as: $CURRENT_USER"

# Function to fix permissions for a channel
fix_channel_permissions() {
    local channel_dir="$1"
    local channel_name=$(basename "$channel_dir")
    
    echo ""
    echo "🔍 Processing channel: $channel_name"
    echo "   Directory: $channel_dir"
    
    if [ ! -d "$channel_dir" ]; then
        echo "   ⚠️  Channel directory does not exist, skipping"
        return
    fi
    
    # Fix directory permissions (755 = rwxr-xr-x)
    echo "   📁 Setting directory permissions..."
    find "$channel_dir" -type d -exec chmod 755 {} \;
    
    # Fix file permissions (644 = rw-r--r--)
    echo "   📄 Setting file permissions..."
    find "$channel_dir" -type f -exec chmod 644 {} \;
    
    # Ensure mimir user/group ownership
    echo "   👥 Setting ownership to mimir:mimir..."
    chown -R mimir:mimir "$channel_dir"
    
    # Check specific subdirectories
    local uploads_dir="$channel_dir/assets/uploads"
    local thumbnails_dir="$channel_dir/assets/thumbnails"
    local data_dir="$channel_dir/data"
    
    if [ -d "$uploads_dir" ]; then
        local image_count=$(find "$uploads_dir" -name "*.jpg" -o -name "*.png" -o -name "*.jpeg" | wc -l)
        echo "   📸 Fixed permissions for $image_count images in uploads/"
    fi
    
    if [ -d "$thumbnails_dir" ]; then
        local thumb_count=$(find "$thumbnails_dir" -name "*.thumb.*" | wc -l)
        echo "   🖼️  Fixed permissions for $thumb_count thumbnails/"
    fi
    
    if [ -d "$data_dir" ]; then
        echo "   💾 Fixed permissions for data/ directory"
    fi
    
    echo "   ✅ Channel $channel_name permissions fixed"
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script should be run with sudo to change file ownership"
    echo "   Example: sudo $0"
    echo ""
    echo "   Will continue with permission changes only..."
    echo ""
fi

# Process all channels
echo ""
echo "🔍 Scanning for channels in $BASE_DIR"

channel_count=0
for channel_dir in "$BASE_DIR"/*; do
    if [ -d "$channel_dir" ]; then
        fix_channel_permissions "$channel_dir"
        ((channel_count++))
    fi
done

echo ""
echo "📊 Summary"
echo "=========="
echo "   📁 Channels processed: $channel_count"
echo "   🔧 Fixed directory permissions: 755 (rwxr-xr-x)"
echo "   📄 Fixed file permissions: 644 (rw-r--r--)"

if [ "$EUID" -eq 0 ]; then
    echo "   👥 Set ownership: mimir:mimir"
else
    echo "   ⚠️  Ownership not changed (not running as root)"
fi

echo ""
echo "🔍 Checking API service user..."

# Check what user the mimir-api service runs as
if systemctl is-active --quiet mimir-api; then
    API_USER=$(ps -o user= -p $(pgrep -f "mimir-api"))
    echo "   🔄 API service is running as: $API_USER"
    if [ "$API_USER" = "mimir" ]; then
        echo "   ✅ API service user matches file ownership"
    else
        echo "   ⚠️  API service user ($API_USER) doesn't match file ownership (mimir)"
        echo "   💡 Consider running API service as 'mimir' user"
    fi
else
    echo "   ⚠️  mimir-api service is not running"
fi

echo ""
echo "🎉 Permission fix complete!"
echo "💡 Restart the mimir-api service if needed:"
echo "   sudo systemctl restart mimir-api"
