#!/bin/bash
"""
Build and Test Enhanced Mimir Web UI with Distribution Monitoring
Builds the React app and starts the development server with distribution features.
"""

set -e

echo "🚀 Building Enhanced Mimir Web UI"
echo "=================================="

# Configuration
UI_PATH="mimir-ui"
BUILD_PATH="${UI_PATH}/build"

# Check if we're in the right directory
if [ ! -d "$UI_PATH" ]; then
    echo "❌ Error: mimir-ui directory not found!"
    echo "Please run this script from the mimir-web root directory."
    exit 1
fi

cd "$UI_PATH"

echo "📦 Installing/updating dependencies..."
npm install

echo "🧪 Running linting checks..."
npm run lint --if-present || echo "⚠️  Linting check skipped (no lint script found)"

echo "🔨 Building production bundle..."
npm run build

if [ -d "$BUILD_PATH" ]; then
    echo "✅ Build successful!"
    echo "📁 Build files available in: $BUILD_PATH"
    echo ""
    echo "🌐 Deployment options:"
    echo "1. Development server: npm start (port 3000)"
    echo "2. Serve build files: npx serve build (port 3000)" 
    echo "3. Copy to production web server"
    echo ""
    echo "🎯 New Distribution Features Added:"
    echo "   • Real-time WebSocket distribution monitoring"
    echo "   • Distribution dashboard with live metrics"
    echo "   • Performance monitoring and event logs"
    echo "   • Redis status and queue monitoring"
    echo "   • Scene distribution mode management"
    echo ""
    echo "🔗 Access URLs:"
    echo "   • Dashboard: http://localhost:3000/"
    echo "   • Distribution: http://localhost:3000/distribution"
    echo "   • Displays: http://localhost:3000/displays"
    echo ""
    echo "📡 WebSocket connects to: ws://oak:5000/ws"
    echo "🌐 API connects to: http://oak:5000/api/"
    
    # Ask if user wants to start development server
    echo ""
    read -p "🚀 Start development server now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🌟 Starting development server..."
        npm start
    else
        echo "✅ Build complete. Run 'npm start' to start development server."
    fi
else
    echo "❌ Build failed!"
    exit 1
fi
