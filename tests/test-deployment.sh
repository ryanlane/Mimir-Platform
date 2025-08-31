#!/bin/bash
# Test script to verify the interactive deployment prompts

set -e

echo "🧪 Testing Mimir API Deployment Script"
echo "======================================"
echo

# Check if the deploy script exists
if [ ! -f "deploy.sh" ]; then
    echo "❌ deploy.sh not found. Please run this from the api-service directory."
    exit 1
fi

echo "✅ Found deploy.sh"

# Check if deploy.sh is executable
if [ ! -x "deploy.sh" ]; then
    echo "⚠️  Making deploy.sh executable..."
    chmod +x deploy.sh
fi

echo "✅ deploy.sh is executable"

# Check required files
required_files=(
    "main.py"
    "app/config.py"
    "requirements.txt"
    "deploy/mimir-api.service"
    "deploy/.env.production"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ Found $file"
    else
        echo "❌ Missing $file"
        exit 1
    fi
done

echo
echo "🎯 All required files present!"
echo

# Check if main.py is the refactored version
if grep -q "create_app" main.py; then
    echo "✅ main.py appears to be the refactored version"
    main_lines=$(wc -l < main.py)
    echo "   Lines in main.py: $main_lines"
else
    echo "❌ main.py doesn't appear to be the refactored version"
    echo "   Make sure you've replaced it with app/main.py"
    exit 1
fi

echo
echo "📋 Deployment script validation complete!"
echo
echo "To test the deployment (dry-run style):"
echo "  1. Run: ./deploy.sh"
echo "  2. Enter a test hostname (e.g., 'test-server.local')"
echo "  3. Enter a username (e.g., 'testuser')"
echo "  4. Choose 'n' when asked to continue to avoid actual deployment"
echo
echo "For actual deployment:"
echo "  1. Run: ./deploy.sh"
echo "  2. Enter your real server hostname"
echo "  3. Enter your username"
echo "  4. Choose 'Y' to proceed with deployment"
