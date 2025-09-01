"""
OpenTelemetry Metrics Configuration
Provides modern observability instrumentation for Mimir API
"""
import time
from typing import Dict, Any
from fastapi import Request, Response
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.metrics import set_meter_provider, get_meter_provider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import make_asgi_app
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global metrics instruments
_meter = None
_http_requests_counter = None
_http_duration_histogram = None
_distribution_operations_counter = None
_discovery_events_counter = None
_active_connections_gauge = None

def setup_metrics():
    """Initialize OpenTelemetry metrics with Prometheus exporter"""
    global _meter, _http_requests_counter, _http_duration_histogram
    global _distribution_operations_counter, _discovery_events_counter, _active_connections_gauge
    
    try:
        # Create Prometheus metric reader for pull-based scraping
        reader = PrometheusMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        set_meter_provider(provider)
        
        # Get meter for this application
        _meter = get_meter_provider().get_meter("mimir-api", version="2.1.0")
        
        # HTTP request metrics
        _http_requests_counter = _meter.create_counter(
            name="http_requests_total",
            unit="1", 
            description="Total HTTP requests"
        )
        
        _http_duration_histogram = _meter.create_histogram(
            name="http_request_duration_seconds",
            unit="s",
            description="HTTP request duration in seconds"
        )
        
        # Distribution system metrics
        _distribution_operations_counter = _meter.create_counter(
            name="distribution_operations_total",
            unit="1",
            description="Total distribution operations (assign, release, claim)"
        )
        
        # Discovery system metrics
        _discovery_events_counter = _meter.create_counter(
            name="discovery_events_total", 
            unit="1",
            description="Total mDNS discovery events (discovered, lost, updated)"
        )
        
        # Active connections gauge
        _active_connections_gauge = _meter.create_up_down_counter(
            name="active_connections",
            unit="1",
            description="Number of active WebSocket connections"
        )
        
        logger.info("OpenTelemetry metrics initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup metrics: {e}")
        return False

def get_prometheus_app():
    """Get the Prometheus metrics ASGI app for mounting"""
    return make_asgi_app()

def record_http_request(method: str, path: str, status_code: int, duration: float):
    """Record HTTP request metrics"""
    if _http_requests_counter and _http_duration_histogram:
        labels = {
            "method": method,
            "path": path,
            "status_code": str(status_code)
        }
        _http_requests_counter.add(1, labels)
        _http_duration_histogram.record(duration, labels)

def record_distribution_operation(operation: str, scene_id: str, display_id: str = None, success: bool = True):
    """Record distribution operation metrics"""
    if _distribution_operations_counter:
        labels = {
            "operation": operation,  # assign, release, claim, reset
            "scene_id": scene_id,
            "status": "success" if success else "error"
        }
        if display_id:
            labels["display_id"] = display_id
        _distribution_operations_counter.add(1, labels)

def record_discovery_event(event_type: str, display_id: str = None):
    """Record mDNS discovery event metrics"""
    if _discovery_events_counter:
        labels = {
            "event_type": event_type,  # discovered, lost, updated
        }
        if display_id:
            labels["display_id"] = display_id
        _discovery_events_counter.add(1, labels)

def update_active_connections(delta: int):
    """Update active WebSocket connections gauge"""
    if _active_connections_gauge:
        _active_connections_gauge.add(delta)

def get_metrics_middleware():
    """Get FastAPI middleware for automatic HTTP metrics collection"""
    
    async def metrics_middleware(request: Request, call_next):
        start_time = time.perf_counter()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.perf_counter() - start_time
        
        # Record metrics
        record_http_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=duration
        )
        
        return response
    
    return metrics_middleware

class MetricsCollector:
    """Utility class for collecting custom business metrics"""
    
    @staticmethod
    def distribution_content_assigned(scene_id: str, display_id: str, content_id: str):
        """Record when content is assigned to a display"""
        record_distribution_operation("assign", scene_id, display_id, True)
    
    @staticmethod 
    def distribution_content_released(scene_id: str, display_id: str, content_id: str):
        """Record when content assignment is released"""
        record_distribution_operation("release", scene_id, display_id, True)
    
    @staticmethod
    def distribution_content_claimed(scene_id: str, display_id: str):
        """Record when a display claims content"""
        record_distribution_operation("claim", scene_id, display_id, True)
    
    @staticmethod
    def distribution_error(scene_id: str, operation: str, error: str):
        """Record distribution operation errors"""
        record_distribution_operation(operation, scene_id, None, False)
    
    @staticmethod
    def discovery_display_found(display_id: str):
        """Record when a new display is discovered"""
        record_discovery_event("discovered", display_id)
    
    @staticmethod
    def discovery_display_lost(display_id: str):
        """Record when a display goes offline"""
        record_discovery_event("lost", display_id)
    
    @staticmethod
    def discovery_display_updated(display_id: str):
        """Record when a display is updated"""
        record_discovery_event("updated", display_id)
    
    @staticmethod
    def websocket_connected():
        """Record WebSocket connection"""
        update_active_connections(1)
    
    @staticmethod
    def websocket_disconnected():
        """Record WebSocket disconnection"""
        update_active_connections(-1)

# Export the collector for easy imports
metrics = MetricsCollector()
