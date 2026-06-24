# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
OpenTelemetry Metrics Collection for Mimir API
Modern observability with OpenTelemetry → Prometheus integration
"""
import logging
import time

from fastapi import Request
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import get_meter_provider, set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import make_asgi_app

logger = logging.getLogger(__name__)

# Initialize OpenTelemetry with Prometheus reader
reader = PrometheusMetricReader()
provider = MeterProvider(metric_readers=[reader])
set_meter_provider(provider)
meter = get_meter_provider().get_meter("mimir")

# Define metrics instruments
http_requests = meter.create_counter(
    name="mimir_http_requests_total",
    unit="1",
    description="Total HTTP requests"
)

http_request_duration = meter.create_histogram(
    name="mimir_http_request_duration_seconds",
    unit="s",
    description="HTTP request duration"
)

discovery_displays_found = meter.create_counter(
    name="mimir_discovery_displays_found_total",
    unit="1",
    description="Total number of displays discovered"
)

discovery_displays_lost = meter.create_counter(
    name="mimir_discovery_displays_lost_total",
    unit="1",
    description="Total number of displays lost"
)

discovery_displays_total = meter.create_up_down_counter(
    name="mimir_discovery_displays_total",
    unit="1",
    description="Current total number of discovered displays"
)

discovery_displays_online = meter.create_up_down_counter(
    name="mimir_discovery_displays_online",
    unit="1",
    description="Current number of online displays"
)

discovery_errors = meter.create_counter(
    name="mimir_discovery_errors_total",
    unit="1",
    description="Total discovery errors"
)

distribution_content_assigned = meter.create_counter(
    name="mimir_distribution_content_assigned_total",
    unit="1",
    description="Total content assignments"
)

distribution_lease_duration = meter.create_histogram(
    name="mimir_distribution_lease_duration_seconds",
    unit="s",
    description="Duration of content leases"
)

distribution_queue_size = meter.create_up_down_counter(
    name="mimir_distribution_queue_size",
    unit="1",
    description="Current size of distribution queues"
)

distribution_errors = meter.create_counter(
    name="mimir_distribution_errors_total",
    unit="1",
    description="Total distribution errors"
)

websocket_connections = meter.create_up_down_counter(
    name="mimir_websocket_connections",
    unit="1",
    description="Current number of WebSocket connections"
)

websocket_messages = meter.create_counter(
    name="mimir_websocket_messages_total",
    unit="1",
    description="Total WebSocket messages sent"
)

redis_operations = meter.create_counter(
    name="mimir_redis_operations_total",
    unit="1",
    description="Total Redis operations"
)

redis_operation_duration = meter.create_histogram(
    name="mimir_redis_operation_duration_seconds",
    unit="s",
    description="Redis operation duration"
)


class MetricsCollector:
    """OpenTelemetry-based metrics collector"""

    def __init__(self):
        logger.info("Metrics collector initialized with OpenTelemetry")

    # Discovery metrics
    def discovery_display_found(self, display_id: str):
        """Record a display discovery"""
        try:
            discovery_displays_found.add(1, {"display_id": display_id})
        except Exception as e:
            logger.error(f"Error recording display found metric: {e}")

    def discovery_display_lost(self, display_id: str):
        """Record a display loss"""
        try:
            discovery_displays_lost.add(1, {"display_id": display_id})
        except Exception as e:
            logger.error(f"Error recording display lost metric: {e}")

    def discovery_display_updated(self, display_id: str):
        """Record a display update"""
        # For now this is a no-op, but could track update frequency
        pass

    def discovery_displays_total(self, count: int):
        """Set total displays count"""
        try:
            # For up-down counters, we need to track the delta
            current = getattr(self, '_last_total_displays', 0)
            delta = count - current
            if delta != 0:
                discovery_displays_total.add(delta)
                self._last_total_displays = count
        except Exception as e:
            logger.error(f"Error setting displays total metric: {e}")

    def discovery_displays_online(self, count: int):
        """Set online displays count"""
        try:
            current = getattr(self, '_last_online_displays', 0)
            delta = count - current
            if delta != 0:
                discovery_displays_online.add(delta)
                self._last_online_displays = count
        except Exception as e:
            logger.error(f"Error setting displays online metric: {e}")

    def discovery_error(self, error_type: str):
        """Record a discovery error"""
        try:
            discovery_errors.add(1, {"error_type": error_type})
        except Exception as e:
            logger.error(f"Error recording discovery error metric: {e}")

    # Distribution metrics
    def distribution_content_assigned(self, scene_id: str, display_id: str, content_id: str = "unknown"):
        """Record content assignment"""
        try:
            distribution_content_assigned.add(1, {
                "scene_id": scene_id,
                "display_id": display_id,
                "content_id": content_id
            })
        except Exception as e:
            logger.error(f"Error recording content assignment metric: {e}")

    def distribution_lease_completed(self, scene_id: str, display_id: str, duration_seconds: float):
        """Record completed content lease"""
        try:
            distribution_lease_duration.record(duration_seconds, {
                "scene_id": scene_id,
                "display_id": display_id
            })
        except Exception as e:
            logger.error(f"Error recording lease duration metric: {e}")

    def distribution_queue_size_updated(self, scene_id: str, queue_type: str, size: int):
        """Update distribution queue size"""
        try:
            queue_key = f"{scene_id}_{queue_type}"
            current = getattr(self, f'_last_queue_size_{queue_key}', 0)
            delta = size - current
            if delta != 0:
                distribution_queue_size.add(delta, {
                    "scene_id": scene_id,
                    "queue_type": queue_type
                })
                setattr(self, f'_last_queue_size_{queue_key}', size)
        except Exception as e:
            logger.error(f"Error recording queue size metric: {e}")

    def distribution_error(self, scene_id: str, operation: str, error_type: str):
        """Record a distribution error"""
        try:
            distribution_errors.add(1, {
                "scene_id": scene_id,
                "operation": operation,
                "error_type": error_type
            })
        except Exception as e:
            logger.error(f"Error recording distribution error metric: {e}")

    # WebSocket metrics
    def websocket_connection_opened(self, connection_id: str):
        """Record WebSocket connection opened"""
        try:
            websocket_connections.add(1, {"connection_id": connection_id})
        except Exception as e:
            logger.error(f"Error recording WebSocket connection opened: {e}")

    def websocket_connection_closed(self, connection_id: str):
        """Record WebSocket connection closed"""
        try:
            websocket_connections.add(-1, {"connection_id": connection_id})
        except Exception as e:
            logger.error(f"Error recording WebSocket connection closed: {e}")

    def websocket_message_sent(self, event_type: str, connection_count: int = 1):
        """Record WebSocket message sent"""
        try:
            websocket_messages.add(connection_count, {"event_type": event_type})
        except Exception as e:
            logger.error(f"Error recording WebSocket message: {e}")

    # Redis metrics
    def redis_operation(self, operation: str, duration_seconds: float, success: bool = True):
        """Record Redis operation"""
        try:
            redis_operations.add(1, {
                "operation": operation,
                "status": "success" if success else "error"
            })
            redis_operation_duration.record(duration_seconds, {"operation": operation})
        except Exception as e:
            logger.error(f"Error recording Redis operation metric: {e}")

    # HTTP metrics
    def http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        try:
            http_requests.add(1, {
                "method": method,
                "endpoint": endpoint,
                "status": str(status)
            })
            http_request_duration.record(duration, {
                "method": method,
                "endpoint": endpoint
            })
        except Exception as e:
            logger.error(f"Error recording HTTP request metric: {e}")


# Global metrics instance
metrics = MetricsCollector()

# Prometheus ASGI app for /metrics endpoint
metrics_app = make_asgi_app()


def setup_metrics() -> bool:
    """Setup OpenTelemetry metrics collection"""
    try:
        logger.info("OpenTelemetry metrics collection setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry metrics: {e}")
        return False


def get_metrics_content():
    """Get metrics content for HTTP endpoint (compatibility function)"""
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        # Use the default registry which the PrometheusMetricReader populates
        metrics_data = generate_latest()
        return metrics_data, CONTENT_TYPE_LATEST
    except Exception as e:
        logger.error(f"Error generating metrics data: {e}")
        return b"", "text/plain"


async def metrics_middleware(request: Request, call_next):
    """Middleware to collect HTTP metrics with OpenTelemetry"""
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

    except Exception:
        duration = time.time() - start_time

        # Record error metrics
        metrics.http_request(
            method=request.method,
            endpoint=str(request.url.path),
            status=500,
            duration=duration
        )

        raise
