"""
Simplified Metrics Collection using Prometheus Client
Provides basic metrics collection without complex OpenTelemetry setup
"""
import logging
from typing import Optional
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time

logger = logging.getLogger(__name__)

# Global metrics registry
metrics_registry = CollectorRegistry()

# Define metrics
discovery_displays_found = Counter(
    'mimir_discovery_displays_found_total',
    'Total number of displays discovered',
    ['display_id'],
    registry=metrics_registry
)

discovery_displays_lost = Counter(
    'mimir_discovery_displays_lost_total', 
    'Total number of displays lost',
    ['display_id'],
    registry=metrics_registry
)

discovery_displays_total = Gauge(
    'mimir_discovery_displays_total',
    'Current total number of discovered displays',
    registry=metrics_registry
)

discovery_displays_online = Gauge(
    'mimir_discovery_displays_online',
    'Current number of online displays',
    registry=metrics_registry
)

discovery_errors = Counter(
    'mimir_discovery_errors_total',
    'Total discovery errors',
    ['error_type'],
    registry=metrics_registry
)

distribution_content_assigned = Counter(
    'mimir_distribution_content_assigned_total',
    'Total content assignments',
    ['channel', 'display'],
    registry=metrics_registry
)

distribution_errors = Counter(
    'mimir_distribution_errors_total',
    'Total distribution errors', 
    ['error_type'],
    registry=metrics_registry
)

http_requests = Counter(
    'mimir_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=metrics_registry
)

http_request_duration = Histogram(
    'mimir_http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    registry=metrics_registry
)


class MetricsCollector:
    """Simple metrics collector using prometheus-client"""
    
    def __init__(self):
        self.registry = metrics_registry
        logger.info("Metrics collector initialized with prometheus-client")
    
    def discovery_display_found(self, display_id: str):
        """Record a display discovery"""
        try:
            discovery_displays_found.labels(display_id=display_id).inc()
        except Exception as e:
            logger.error(f"Error recording display found metric: {e}")
    
    def discovery_display_lost(self, display_id: str):
        """Record a display loss"""
        try:
            discovery_displays_lost.labels(display_id=display_id).inc()
        except Exception as e:
            logger.error(f"Error recording display lost metric: {e}")
    
    def discovery_display_updated(self, display_id: str):
        """Record a display update (no-op for now)"""
        pass
    
    def discovery_displays_total(self, count: int):
        """Set total displays count"""
        try:
            discovery_displays_total.set(count)
        except Exception as e:
            logger.error(f"Error setting displays total metric: {e}")
    
    def discovery_displays_online(self, count: int):
        """Set online displays count"""
        try:
            discovery_displays_online.set(count)
        except Exception as e:
            logger.error(f"Error setting displays online metric: {e}")
    
    def discovery_error(self, error_type: str):
        """Record a discovery error"""
        try:
            discovery_errors.labels(error_type=error_type).inc()
        except Exception as e:
            logger.error(f"Error recording discovery error metric: {e}")
    
    def distribution_content_assigned(self, channel: str, display: str):
        """Record content assignment"""
        try:
            distribution_content_assigned.labels(channel=channel, display=display).inc()
        except Exception as e:
            logger.error(f"Error recording content assignment metric: {e}")
    
    def distribution_error(self, error_type: str):
        """Record a distribution error"""
        try:
            distribution_errors.labels(error_type=error_type).inc()
        except Exception as e:
            logger.error(f"Error recording distribution error metric: {e}")
    
    def http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        try:
            http_requests.labels(method=method, endpoint=endpoint, status=str(status)).inc()
            http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)
        except Exception as e:
            logger.error(f"Error recording HTTP request metric: {e}")
    
    def get_metrics_data(self) -> bytes:
        """Get metrics in Prometheus format"""
        try:
            return generate_latest(self.registry)
        except Exception as e:
            logger.error(f"Error generating metrics data: {e}")
            return b""


# Global metrics instance
metrics = MetricsCollector()


def setup_metrics() -> bool:
    """Setup metrics collection (simplified)"""
    try:
        logger.info("Metrics collection setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to setup metrics: {e}")
        return False


def get_metrics_content():
    """Get metrics content for HTTP endpoint"""
    return metrics.get_metrics_data(), CONTENT_TYPE_LATEST


async def metrics_middleware(request, call_next):
    """Middleware to collect HTTP metrics"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Record metrics
        metrics.http_request(
            method=request.method,
            endpoint=str(request.url.path),
            status=response.status_code,
            duration=duration
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        
        # Record error metrics
        metrics.http_request(
            method=request.method,
            endpoint=str(request.url.path),
            status=500,
            duration=duration
        )
        
        raise
