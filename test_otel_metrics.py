#!/usr/bin/env python3
"""
Test script for OpenTelemetry metrics integration
Verifies that the /metrics endpoint is working correctly
"""

import requests
import time

def test_metrics_endpoint():
    """Test the Prometheus metrics endpoint"""
    print("🧪 Testing OpenTelemetry metrics endpoint...")
    
    try:
        # Test the metrics endpoint
        response = requests.get("http://localhost:5000/metrics")
        
        if response.status_code == 200:
            print("✅ Metrics endpoint is accessible")
            
            # Check for expected metrics
            metrics_text = response.text
            expected_metrics = [
                "mimir_http_requests_total",
                "mimir_discovery_displays_found_total", 
                "mimir_distribution_content_assigned_total",
                "mimir_websocket_connections"
            ]
            
            found_metrics = []
            for metric in expected_metrics:
                if metric in metrics_text:
                    found_metrics.append(metric)
                    print(f"  ✅ Found metric: {metric}")
                else:
                    print(f"  ⚠️  Missing metric: {metric}")
            
            print(f"\n📊 Found {len(found_metrics)}/{len(expected_metrics)} expected metrics")
            
            # Show a sample of the metrics output
            print("\n📋 Sample metrics output:")
            print("=" * 50)
            lines = metrics_text.split('\n')
            for i, line in enumerate(lines[:20]):  # First 20 lines
                if line.strip() and not line.startswith('#'):
                    print(f"  {line}")
            print("=" * 50)
            
        else:
            print(f"❌ Metrics endpoint returned status {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to http://localhost:5000")
        print("Make sure the Mimir API server is running")
    except Exception as e:
        print(f"❌ Error testing metrics: {e}")

def test_api_requests():
    """Generate some API requests to create metrics data"""
    print("\n🔄 Generating API requests to create metrics data...")
    
    try:
        # Test various endpoints to generate HTTP metrics
        endpoints = [
            "/api/health",
            "/api/scenes",
            "/api/channels", 
            "/api/displays"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"http://localhost:5000{endpoint}")
                print(f"  📡 {endpoint}: {response.status_code}")
            except Exception as e:
                print(f"  ❌ {endpoint}: {e}")
                
        print("✅ Generated API requests for metrics collection")
        
    except Exception as e:
        print(f"❌ Error generating API requests: {e}")

if __name__ == "__main__":
    print("🎯 OpenTelemetry Metrics Test for Mimir API")
    print("=" * 50)
    
    # Test the metrics endpoint
    test_metrics_endpoint()
    
    # Generate some API traffic
    test_api_requests()
    
    # Wait and test metrics again to see the data
    print("\n⏱️  Waiting 2 seconds then checking metrics again...")
    time.sleep(2)
    test_metrics_endpoint()
    
    print("\n🎉 Testing complete!")
    print("You can view metrics in Prometheus by adding this scrape config:")
    print("""
scrape_configs:
  - job_name: 'mimir-api'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
""")
