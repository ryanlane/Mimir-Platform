"""
MQTT Presence Service
Implements instant online/offline detection using MQTT Last Will & Testament (LWT)
Replaces polling-based timeout detection with event-driven presence
"""
import asyncio
import json
import socket
from typing import TYPE_CHECKING  # retained for future type-only hints
from collections.abc import Callable
from datetime import datetime, timezone
from app.services.mqtt_ws_bridge import forward_mqtt_message
from app.services.mqtt_debug_stats import mqtt_debug_stats

if TYPE_CHECKING:  # pragma: no cover
    pass

try:
    from aiomqtt import Client, MqttError
    AIOMQTT_AVAILABLE = True
except ImportError:
    AIOMQTT_AVAILABLE = False

from app.config import settings
from app.core.logging import get_logger

# Import metrics for instrumentation
try:
    from app.core.metrics import metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

logger = get_logger(__name__)


class MqttPresenceService:
    """MQTT-based presence detection service using Last Will & Testament"""
    
    def __init__(self):
        self.broker_host = getattr(settings, 'mqtt_broker_host', 'localhost')
        self.broker_port = getattr(settings, 'mqtt_broker_port', 1883)
        self.client_id = f"mimir-api-{socket.gethostname()}"
        
        # Presence tracking
        self.online_devices: set[str] = set()
        self.device_metadata: dict[str, dict] = {}

        # Callbacks for presence events
        self.presence_callbacks: set[Callable] = set()

        # Client state
        self.client: Client | None = None
        self.is_running = False
        # Simple per-topic debounce (topic -> last_forward_ts)
        self._forward_last: dict[str, float] = {}
        self._debounce_seconds: float = float(getattr(settings, "mqtt_ws_debounce_seconds", 0.75))
        
        logger.info(f"MQTT Presence Service initialized - Broker: {self.broker_host}:{self.broker_port}")
    
    def add_presence_callback(self, callback: Callable):
        """Add callback for presence events (device_id, event_type, metadata)"""
        self.presence_callbacks.add(callback)
    
    def remove_presence_callback(self, callback: Callable):
        """Remove presence callback"""
        self.presence_callbacks.discard(callback)
    
    def _notify_presence_callbacks(self, device_id: str, event_type: str, metadata: dict | None = None):
        """Notify all presence callbacks of an event"""
        for callback in self.presence_callbacks:
            try:
                callback(device_id, event_type, metadata or {})
            except Exception as e:
                logger.error(f"Error in presence callback: {e}")
    
    async def start(self):
        """Start the MQTT presence monitoring service"""
        if not AIOMQTT_AVAILABLE:
            logger.error("asyncio-mqtt not available - MQTT presence disabled")
            return False

        if self.is_running:
            logger.warning("MQTT presence service already running")
            return True

        try:
            # Just start the loop - client connection happens in the loop
            self.is_running = True
            self._loop_task = asyncio.create_task(self._mqtt_client_loop())
            logger.info("MQTT presence service started")
            return True

        except Exception as e:
            logger.error(f"Failed to start MQTT presence service: {e}")
            self.is_running = False
            return False

    
    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        # Cancel the main loop task
        loop_task = getattr(self, "_loop_task", None)
        if loop_task and not loop_task.done():
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
        logger.info("MQTT presence service stopped")

    
    async def _mqtt_client_loop(self):
        """Main MQTT client loop with automatic reconnection"""
        while self.is_running:
            try:
                # Set up Last Will & Testament for this API instance
                will_topic = f"mimir/api/{self.client_id}/status"
                # Prepare last will (future aiomqtt API may use explicit config method)
                
                async with Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    identifier=self.client_id,  # Changed from client_id to identifier
                    # Note: Will configuration moved to separate method in v1.0
                ) as client:
                    self.client = client
                    
                    # Publish that this API instance is online
                    online_payload = json.dumps({
                        "status": "online",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "version": "2.1.0"
                    })
                    await client.publish(will_topic, online_payload, qos=1, retain=True)
                    
                    # Subscribe to all device presence topics
                    # Broaden subscription to all mimir hierarchy for debug observability
                    await client.subscribe("mimir/#", qos=0)
                    logger.info("MQTT client connected - monitoring all topics under mimir/# (debug mode)")
                    
                    # Record successful connection
                    if METRICS_AVAILABLE:
                        metrics.redis_operation("mqtt_connect", 0.0, True)
                    
                    # Message processing loop
                    async for message in client.messages:
                        await self._handle_mqtt_message(message)
                        
            except MqttError as e:
                logger.error(f"MQTT connection error: {e}")
                if METRICS_AVAILABLE:
                    metrics.redis_operation("mqtt_connect", 0.0, False)
                    
            except Exception as e:
                logger.error(f"Unexpected error in MQTT client loop: {e}")
                
            # Wait before reconnecting
            if self.is_running:
                logger.info("Reconnecting to MQTT broker in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _handle_mqtt_message(self, message):
        """Handle incoming MQTT presence messages"""
        try:
            full_topic = message.topic.value
            payload_bytes = message.payload
            if not payload_bytes:
                logger.warning(f"Received empty MQTT payload on topic {full_topic}")
                return

            mqtt_debug_stats.record_received(full_topic, payload_bytes)

            # Verbose trace for diagnostics (INFO to surface during incident)
            logger.info("[mqtt-presence] recv topic=%s bytes=%d", full_topic, len(payload_bytes))

            topic_parts = full_topic.split('/')
            # Expect at least mimir/<device>/<type>
            if len(topic_parts) < 3:
                return

            device_id = topic_parts[1]
            message_type = topic_parts[2]
            if not device_id:
                return
            if device_id.startswith('api-'):
                return

            try:
                payload = json.loads(payload_bytes.decode())
            except Exception:
                # Non JSON payloads still forwarded; skip presence semantics
                payload = None

            # Forward raw frame (bridge) with debounce
            await self._maybe_forward(full_topic, payload_bytes, qos=None, retain=None)

            if payload and message_type == "status":
                await self._handle_status_message(device_id, payload)
            elif payload and message_type == "heartbeat":
                await self._handle_heartbeat_message(device_id, payload)
            elif payload and message_type == "evt":
                await self._handle_event_message(device_id, payload)

        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")
    
    async def _handle_status_message(self, device_id: str, payload: dict):
        """Handle device status messages (online/offline)"""
        status = payload.get("status", "unknown")
        timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
        
        if status == "online":
            if device_id not in self.online_devices:
                self.online_devices.add(device_id)
                self.device_metadata[device_id] = {
                    "last_seen": timestamp,
                    "last_status": "online",
                    "first_seen": timestamp,
                    **payload
                }
                
                logger.info(f"Device came online: {device_id}")
                self._notify_presence_callbacks(device_id, "online", self.device_metadata[device_id])
                
                # Record metrics
                if METRICS_AVAILABLE:
                    metrics.discovery_display_found(device_id)
            else:
                # Update existing device metadata
                if device_id in self.device_metadata:
                    self.device_metadata[device_id].update({
                        "last_seen": timestamp,
                        "last_status": "online"
                    })
        
        elif status == "offline":
            if device_id in self.online_devices:
                self.online_devices.remove(device_id)
                
                if device_id in self.device_metadata:
                    self.device_metadata[device_id].update({
                        "last_seen": timestamp,
                        "last_status": "offline",
                        "offline_reason": payload.get("reason", "graceful_disconnect")
                    })
                
                logger.info(f"Device went offline: {device_id} (reason: {payload.get('reason', 'unknown')})")
                self._notify_presence_callbacks(device_id, "offline", self.device_metadata.get(device_id, {}))
                
                # Record metrics
                if METRICS_AVAILABLE:
                    metrics.discovery_display_lost(device_id)

    async def _maybe_forward(self, topic: str, payload_bytes: bytes, qos: int | None, retain: bool | None):
        """Forward to websocket dashboards respecting debounce window per topic."""
        try:
            now = asyncio.get_event_loop().time()
            last = self._forward_last.get(topic)
            if last is not None and (now - last) < self._debounce_seconds:
                # Log debounce suppression at INFO (low frequency per topic ~0.75s window)
                logger.info("[mqtt-presence] debounce skip topic=%s delta_ms=%.1f window_ms=%.0f", topic, (now - last) * 1000.0, self._debounce_seconds * 1000.0)
                return
            self._forward_last[topic] = now
            await forward_mqtt_message(topic=topic, payload_bytes=payload_bytes, qos=qos, retain=retain)
            mqtt_debug_stats.record_forwarded(topic, payload_bytes)
            logger.info("[mqtt-presence] forwarded topic=%s", topic)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("MQTT presence bridge forward error: %s", e)


    async def _handle_heartbeat_message(self, device_id: str, payload: dict):
        """Handle device heartbeat messages"""
        logger.info(f"Received heartbeat from device {device_id}: {payload}")
        
        timestamp_str = payload.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        
        if device_id in self.device_metadata:
            self.device_metadata[device_id]["last_heartbeat"] = timestamp.isoformat()
            self.device_metadata[device_id]["heartbeat_data"] = payload
        
        # Bridge to discovery service for heartbeat updates
        try:
            from app.services.mdns_discovery import mdns_discovery_service
            logger.info(f"Bridging heartbeat to discovery service for device {device_id}")
            mdns_discovery_service.update_display_heartbeat(device_id, timestamp, payload)
            logger.info(f"Successfully bridged heartbeat for device {device_id}")
        except Exception as e:
            logger.error(f"Failed to bridge heartbeat to discovery service for device {device_id}: {e}", exc_info=True)
        
        # Heartbeats indicate the device is active
        if device_id not in self.online_devices:
            # Device sent heartbeat but wasn't marked online - mark it online
            self.online_devices.add(device_id)
            logger.info(f"Device marked online via heartbeat: {device_id}")
            self._notify_presence_callbacks(device_id, "heartbeat_online", {"timestamp": timestamp.isoformat()})
    
    async def _handle_event_message(self, device_id: str, payload: dict):
        """Handle device event messages for immediate scene assignment updates"""
        event_type = payload.get("type")
        
        # Handle acknowledgment events that contain scene assignment data
        if event_type == "ack" and payload.get("ok"):
            scene_id = payload.get("scene_id")
            subchannel_id = payload.get("subchannel_id")
            
            # If this acknowledgment contains scene assignment data, update immediately
            if scene_id is not None:
                timestamp = datetime.now(timezone.utc)
                
                # Create or update device metadata
                if device_id not in self.device_metadata:
                    self.device_metadata[device_id] = {
                        "last_seen": timestamp.isoformat(),
                        "last_status": "online",
                        "first_seen": timestamp.isoformat()
                    }
                
                # Store the event data
                self.device_metadata[device_id]["last_event"] = payload
                self.device_metadata[device_id]["last_event_timestamp"] = timestamp.isoformat()
                
                # Create scene assignment data to pass to mDNS discovery
                scene_data = {
                    "scene_id": scene_id,
                    "subchannel_id": subchannel_id,
                    "timestamp": timestamp.isoformat(),
                    "source": "event_ack"
                }
                
                # Bridge to discovery service for immediate scene assignment update
                from app.services.mdns_discovery import mdns_discovery_service
                mdns_discovery_service.update_display_heartbeat(device_id, timestamp, scene_data)
                
                logger.info(f"Updated scene assignment from event for {device_id}: scene_id={scene_id}, subchannel_id={subchannel_id}")
    
    async def publish_device_status(self, device_id: str, status: str, metadata: dict | None = None):
        """Publish status for a device (useful for testing or manual control)"""
        if not self.client:
            logger.warning("Cannot publish device status - MQTT client not connected")
            return False
        
        try:
            topic = f"mimir/{device_id}/status"
            payload = {
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(metadata or {})
            }
            
            await self.client.publish(topic, json.dumps(payload), qos=1, retain=True)
            logger.debug(f"Published status for {device_id}: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing device status: {e}")
            return False
    
    def get_online_devices(self) -> set[str]:
        """Get set of currently online device IDs"""
        return self.online_devices.copy()
    
    def get_device_metadata(self, device_id: str) -> dict | None:
        """Get metadata for a specific device"""
        return self.device_metadata.get(device_id)
    
    def get_all_device_metadata(self) -> dict[str, dict]:
        """Get metadata for all known devices"""
        return self.device_metadata.copy()
    
    def is_device_online(self, device_id: str) -> bool:
        """Check if a specific device is currently online"""
        return device_id in self.online_devices
    
    def get_presence_stats(self) -> dict:
        """Get presence statistics"""
        total_devices = len(self.device_metadata)
        online_devices = len(self.online_devices)
        offline_devices = total_devices - online_devices
        
        return {
            "total_devices": total_devices,
            "online_devices": online_devices,
            "offline_devices": offline_devices,
            "mqtt_connected": self.client is not None and self.is_running,
            "broker": f"{self.broker_host}:{self.broker_port}"
        }

    # ------------------------------------------------------------------
    # Debug helpers (NOT part of public API; exposed via debug route only)
    # ------------------------------------------------------------------
    def get_forward_state(self, limit: int = 25) -> dict:
        """Return snapshot of recent forward timings and debounce config.

        Parameters
        ----------
        limit: int
            Maximum number of topics to include from the internal forward map.
        """
        now = asyncio.get_event_loop().time()
        items = []
        for t, ts in list(self._forward_last.items())[:limit]:
            items.append({
                "topic": t,
                "age_ms": round((now - ts) * 1000.0, 1)
            })
        return {
            "debounce_seconds": self._debounce_seconds,
            "tracked_topics": len(self._forward_last),
            "sample": items,
        }


# Global service instance
mqtt_presence_service = MqttPresenceService()


# Compatibility functions for existing mDNS discovery integration
async def setup_mqtt_integration():
    """Setup MQTT integration with existing discovery system"""
    try:
        # Start the MQTT presence service
        success = await mqtt_presence_service.start()
        
        if success:
            # Add callback to bridge MQTT presence to existing discovery system
            mqtt_presence_service.add_presence_callback(_bridge_to_discovery_system)
            logger.info("MQTT presence integration setup completed")
        else:
            logger.warning("MQTT presence service failed to start")
            
        return success
        
    except Exception as e:
        logger.error(f"Failed to setup MQTT integration: {e}")
        return False


def _bridge_to_discovery_system(device_id: str, event_type: str, metadata: dict):
    """Bridge MQTT presence events to existing discovery system"""
    try:
        # Import here to avoid circular imports
    # (Import of mdns_discovery_service intentionally omitted to avoid circular + unused warning)
        
        if event_type == "online":
            logger.info(f"MQTT: Device {device_id} came online - notifying discovery system")
            # You can extend this to update the mDNS discovery service state
            
        elif event_type == "offline":
            logger.info(f"MQTT: Device {device_id} went offline - notifying discovery system")
            # You can extend this to update the mDNS discovery service state
            
    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"Error bridging MQTT presence to discovery system: {e}")
