#!/bin/bash
# Sync Photo Frame Channel from source to API service for testing
# This ensures the API service always has the latest version from the source project

SOURCE_DIR="/mnt/c/Users/futil/projects/github/image-frame-channel-mimir/channels/photo_frame"
TARGET_DIR="/mnt/c/Users/futil/projects/github/mimir-api/api-service/channels/photo_frame"

echo "📋 Syncing Photo Frame Channel..."
echo "   Source: $SOURCE_DIR"
echo "   Target: $TARGET_DIR"

# Check if source exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Source directory not found: $SOURCE_DIR"
    exit 1
fi

# Create target directory if it doesn't exist
if [ ! -d "$TARGET_DIR" ]; then
    echo "📁 Creating target directory: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
fi

# Sync files (excluding test files and temp data)
echo "🔄 Syncing files..."
rsync -av --delete \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    --exclude="test_*.py" \
    --exclude="data/photo_frame.db" \
    --exclude="data/galleries.json" \
    --exclude="assets/uploads/*" \
    --exclude="current/*" \
    "$SOURCE_DIR/" "$TARGET_DIR/"

echo "✅ Sync completed!"
echo ""
echo "📝 Files synced:"
echo "   - channel.py (with gallery support)"
echo "   - config.json"
echo "   - utils/ (image processor, database)"
echo "   - ui/ (web components)"
echo "   - requirements.txt"
echo ""
echo "📝 Files excluded:"
echo "   - Test databases and uploaded content"
echo "   - Python cache files"
echo "   - Test-specific files"
echo ""
echo "🔧 To run API tests:"
echo "   cd /mnt/c/Users/futil/projects/github/mimir-api/api-service"
echo "   python3 -m pytest channels/photo_frame/test_*.py"
