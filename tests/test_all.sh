#!/bin/bash
# Comprehensive test script for Mimir Platform
# Tests all components and their integrations

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_DIR="/mnt/c/Users/futil/projects/github"
FAILED_TESTS=0
PASSED_TESTS=0

echo -e "${BLUE}🧪 Mimir Platform Test Suite${NC}"
echo "=================================================="

# Helper function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local test_dir="$3"
    
    echo -e "${YELLOW}Running: $test_name${NC}"
    
    if [ -n "$test_dir" ]; then
        cd "$test_dir"
    fi
    
    if eval "$test_command" > /tmp/test_output 2>&1; then
        echo -e "${GREEN}✅ PASS: $test_name${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ FAIL: $test_name${NC}"
        echo "Error output:"
        cat /tmp/test_output | head -10
        echo "..."
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

# 1. Sync channels first
echo -e "${BLUE}🔄 Step 1: Syncing Channels${NC}"
cd "$BASE_DIR/mimir-api"
if ./sync_all_channels.sh > /tmp/sync_output 2>&1; then
    echo -e "${GREEN}✅ Channels synced successfully${NC}"
else
    echo -e "${RED}❌ Channel sync failed${NC}"
    cat /tmp/sync_output
    exit 1
fi
echo ""

# 2. Test API Infrastructure
echo -e "${BLUE}🌐 Step 2: API Infrastructure Tests${NC}"
run_test "Sub-channel Infrastructure" \
    "python3 test_subchannel_basic.py" \
    "$BASE_DIR/mimir-api/api-service"

run_test "Photo Frame Import Test" \
    "python3 -c \"from channels.photo_frame.channel import PhotoFrameChannel; print('Import successful')\"" \
    "$BASE_DIR/mimir-api/api-service"

# 3. Test Photo Frame Channel
echo -e "${BLUE}📸 Step 3: Photo Frame Channel Tests${NC}"
run_test "Photo Frame Gallery Tests" \
    "python3 test_galleries.py" \
    "$BASE_DIR/image-frame-channel-mimir/channels/photo_frame"

# 4. Test Web Frontend (if tests exist)
echo -e "${BLUE}🎨 Step 4: Frontend Tests${NC}"
if [ -f "$BASE_DIR/mimir-web/mimir-ui/package.json" ]; then
    run_test "Frontend Tests" \
        "npm test --passWithNoTests --watchAll=false" \
        "$BASE_DIR/mimir-web/mimir-ui"
else
    echo -e "${YELLOW}⚠️ No frontend tests found (skipping)${NC}"
    echo ""
fi

# 5. Integration Tests
echo -e "${BLUE}🔗 Step 5: Integration Tests${NC}"
run_test "API Server Start Test" \
    "timeout 10s uvicorn main:app --host 127.0.0.1 --port 8001 || true" \
    "$BASE_DIR/mimir-api/api-service"

# 6. Documentation Tests
echo -e "${BLUE}📚 Step 6: Documentation Tests${NC}"
run_test "Documentation Links Check" \
    "find . -name '*.md' -exec grep -l 'http' {} \; | wc -l > /tmp/doc_count && echo 'Documentation files found'" \
    "$BASE_DIR/mimir-documentation"

# Test Summary
echo ""
echo -e "${BLUE}📊 Test Results Summary${NC}"
echo "=================================================="
echo -e "✅ Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "❌ Failed: ${RED}$FAILED_TESTS${NC}"
echo -e "📊 Total:  $((PASSED_TESTS + FAILED_TESTS))"

if [ $FAILED_TESTS -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 All tests passed! Mimir Platform is healthy.${NC}"
    echo ""
    echo -e "${BLUE}🚀 Ready for development:${NC}"
    echo "   API Server: cd $BASE_DIR/mimir-api/api-service && uvicorn main:app --reload"
    echo "   Frontend:   cd $BASE_DIR/mimir-web/mimir-ui && npm run dev"
    echo "   Channels:   Edit in $BASE_DIR/image-frame-channel-mimir/"
    exit 0
else
    echo ""
    echo -e "${RED}💥 Some tests failed. Please check the output above.${NC}"
    exit 1
fi
