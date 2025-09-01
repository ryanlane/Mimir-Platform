# OpenTelemetry Metrics Implementation for Mimir API

## 🎯 Overview

This implementation replaces the basic `prometheus-client` metrics with modern OpenTelemetry instrumentation, following the recommendations in the modernization document.

## ✅ What's Been Implemented

### 1. **OpenTelemetry Metrics Collection** (`app/core/metrics.py`)

- **Replaced** basic prometheus-client with OpenTelemetry SDK
- **Added** comprehensive metric instruments:
  - HTTP request counters and duration histograms
  - Discovery metrics (displays found/lost/total/online)
  - Distribution metrics (content assignments, lease duration, queue sizes)
  - WebSocket metrics (connections, messages)
  - Redis operation metrics

### 2. **Prometheus Integration**

- **Added** PrometheusMetricReader for seamless Prometheus scraping
- **Mounted** `/metrics` endpoint using prometheus-client's ASGI app
- **Maintains** compatibility with existing Prometheus infrastructure

### 3. **Service Instrumentation**

- **WebSocket Service**: Connection tracking, message counting
- **Distribution Service**: Content assignments, queue monitoring
- **HTTP Middleware**: Request/response metrics for all endpoints

## 🚀 Installation & Setup

### Install Dependencies

```bash
cd api-service
pip install \
    "opentelemetry-api>=1.21.0" \
    "opentelemetry-sdk>=1.21.0" \
    "opentelemetry-exporter-prometheus>=1.21.0" \
    "opentelemetry-instrumentation-fastapi>=0.42b0"
```

Or run the install script:

```bash
./install_otel_dependencies.sh
```

### Start the API Server

```bash
cd api-service
python main.py
```

### Test the Metrics Endpoint

```bash
# Test the endpoint
curl http://localhost:5000/metrics

# Or use the test script
python ../test_otel_metrics.py
```

## 📊 Available Metrics

### HTTP Metrics
- `mimir_http_requests_total` - Total HTTP requests by method/endpoint/status
- `mimir_http_request_duration_seconds` - Request duration histogram

### Discovery Metrics
- `mimir_discovery_displays_found_total` - Displays discovered
- `mimir_discovery_displays_lost_total` - Displays lost
- `mimir_discovery_displays_total` - Current total displays
- `mimir_discovery_displays_online` - Current online displays
- `mimir_discovery_errors_total` - Discovery errors

### Distribution Metrics
- `mimir_distribution_content_assigned_total` - Content assignments
- `mimir_distribution_lease_duration_seconds` - Lease duration histogram
- `mimir_distribution_queue_size` - Current queue sizes
- `mimir_distribution_errors_total` - Distribution errors

### WebSocket Metrics
- `mimir_websocket_connections` - Current WebSocket connections
- `mimir_websocket_messages_total` - Messages sent by event type

### Redis Metrics
- `mimir_redis_operations_total` - Redis operations by type/status
- `mimir_redis_operation_duration_seconds` - Redis operation duration

## 🔧 Prometheus Configuration

Use the provided `prometheus.yml` configuration:

```yaml
scrape_configs:
  - job_name: 'mimir-api'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
```

## 🎯 Benefits Achieved

1. **Modern Observability**: Industry-standard OpenTelemetry metrics
2. **Prometheus Compatible**: Seamless integration with existing Prometheus setups
3. **Rich Context**: Metrics include labels for filtering and aggregation
4. **Future-Proof**: Can easily export to other observability platforms
5. **Performance**: Efficient metric collection with minimal overhead

## 🔄 Next Steps

The remaining modernization tasks from the document:

1. **APScheduler Implementation** - Replace background task loops
2. **MQTT Presence** - Event-driven display online/offline detection
3. **Redis Streams** - Upgrade event distribution architecture
4. **Dashboard Updates** - Add Prometheus time-series charts to UI

## 📈 Sample Metrics Output

```prometheus
# HELP mimir_http_requests_total Total HTTP requests
# TYPE mimir_http_requests_total counter
mimir_http_requests_total{endpoint="/api/health",method="GET",status="200"} 5.0

# HELP mimir_websocket_connections Current number of WebSocket connections
# TYPE mimir_websocket_connections gauge
mimir_websocket_connections{connection_id="dashboard_140"} 1.0

# HELP mimir_distribution_content_assigned_total Total content assignments
# TYPE mimir_distribution_content_assigned_total counter
mimir_distribution_content_assigned_total{content_id="image_001",display_id="pi-display-1",scene_id="gallery"} 3.0
```

## 🧪 Testing

The implementation includes comprehensive metrics coverage that will automatically start collecting data once the API receives traffic. Use the test script to verify functionality and generate sample metrics data.

---

**Status**: ✅ Complete - OpenTelemetry metrics fully implemented and ready for production use.
