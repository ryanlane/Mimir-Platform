#!/bin/bash
# Quick development setup for Mimir Platform
# Sets up the development environment with all necessary components

set -e

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Mimir Platform Quick Setup${NC}"
echo "=================================================="

BASE_DIR="/mnt/c/Users/futil/projects/github"

# 1. Sync channels
echo -e "${YELLOW}🔄 Syncing channels...${NC}"
cd "$BASE_DIR/mimir-api"
./sync_all_channels.sh

# 2. Quick validation
echo -e "${YELLOW}🧪 Running quick validation...${NC}"
cd "$BASE_DIR/mimir-api/api-service"
python3 -c "
from channels.photo_frame.channel import PhotoFrameChannel
print('✅ Photo Frame channel import successful')

import sys
sys.path.append('.')
from base_channel import BaseChannel
from subchannel_manager import SubChannelManager
print('✅ Sub-channel infrastructure available')
"

echo ""
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo -e "${BLUE}🎯 Development Commands:${NC}"
echo ""
echo "📝 Open unified workspace:"
echo "   code $BASE_DIR/mimir-documentation/mimir-platform.code-workspace"
echo ""
echo "🌐 Start API server:"
echo "   cd $BASE_DIR/mimir-api/api-service"
echo "   uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "🎨 Start frontend:"
echo "   cd $BASE_DIR/mimir-web/mimir-ui" 
echo "   npm run dev"
echo ""
echo "🔄 Sync channels after changes:"
echo "   cd $BASE_DIR/mimir-api"
echo "   ./sync_all_channels.sh"
echo ""
echo "🧪 Run comprehensive tests:"
echo "   cd $BASE_DIR/mimir-api"
echo "   ./test_all.sh"
echo ""
echo -e "${GREEN}🎉 Happy coding!${NC}"
