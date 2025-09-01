#!/bin/bash

# Script to install OpenTelemetry dependencies for Mimir API modernization
# Run from the api-service directory

echo "🚀 Installing OpenTelemetry dependencies for Mimir API..."

cd api-service

# Install the new dependencies
pip install \
    "opentelemetry-api>=1.21.0" \
    "opentelemetry-sdk>=1.21.0" \
    "opentelemetry-exporter-prometheus>=1.21.0" \
    "opentelemetry-instrumentation-fastapi>=0.42b0"

echo "✅ OpenTelemetry dependencies installed!"

# Test the metrics endpoint
echo "🧪 Starting test server to verify metrics endpoint..."
echo "After the server starts, you can test the metrics endpoint at:"
echo "  http://localhost:5000/metrics"
echo ""
echo "Press Ctrl+C to stop the test server"

# Start the server
python main.py
