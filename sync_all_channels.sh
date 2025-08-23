#!/bin/bash
# Enhanced sync script for all Mimir Platform channels
# Keeps API service channels synchronized with their source repositories

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_DIR="/mnt/c/Users/futil/projects/github"
API_CHANNELS_DIR="$BASE_DIR/mimir-api/api-service/channels"

echo -e "${BLUE}🔄 Mimir Platform Channel Sync${NC}"
echo "=================================================="

# Sync Photo Frame Channel
echo -e "${YELLOW}📸 Syncing Photo Frame Channel...${NC}"
SOURCE_DIR="$BASE_DIR/image-frame-channel-mimir/channels/photo_frame"
TARGET_DIR="$API_CHANNELS_DIR/photo_frame"

if [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}❌ Photo Frame source not found: $SOURCE_DIR${NC}"
    exit 1
fi

echo "   Source: $SOURCE_DIR"
echo "   Target: $TARGET_DIR"

# Create target directory if needed
mkdir -p "$TARGET_DIR"

# Sync with exclusions
rsync -av --delete \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    --exclude="test_*.py" \
    --exclude="data/photo_frame.db" \
    --exclude="data/galleries.json" \
    --exclude="assets/uploads/*" \
    --exclude="current/*" \
    --exclude=".git/" \
    "$SOURCE_DIR/" "$TARGET_DIR/"

echo -e "${GREEN}✅ Photo Frame Channel synced${NC}"

# TODO: Add other channels here as they're created
# echo -e "${YELLOW}🌤️ Syncing Weather Channel...${NC}"
# SOURCE_DIR="$BASE_DIR/weather-channel-mimir/channels/weather"
# TARGET_DIR="$API_CHANNELS_DIR/weather"
# if [ -d "$SOURCE_DIR" ]; then
#     rsync -av --delete --exclude="__pycache__/" "$SOURCE_DIR/" "$TARGET_DIR/"
#     echo -e "${GREEN}✅ Weather Channel synced${NC}"
# else
#     echo -e "${YELLOW}⚠️ Weather Channel source not found (not created yet)${NC}"
# fi

echo ""
echo -e "${GREEN}🎯 Channel Sync Summary${NC}"
echo "=================================================="
echo "✅ Photo Frame Channel: Synced"
echo "📝 Excluded: Cache files, test databases, uploaded content"
echo ""
echo -e "${BLUE}🔧 Next Steps:${NC}"
echo "   cd $BASE_DIR/mimir-api/api-service"
echo "   python3 test_subchannel_basic.py  # Test infrastructure"
echo "   python3 -c \"from channels.photo_frame.channel import PhotoFrameChannel; print('✅ Import successful')\""
echo ""
echo -e "${GREEN}✨ All channels synchronized!${NC}"
