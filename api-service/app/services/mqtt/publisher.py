"""
MQTT publisher utilities for scene assignment and display commands.

Deduplication
-------------
This module de-duplicates identical commands per device/topic by hashing the
payload with volatile fields removed (timestamp, assignment_id, sequence). If an
identical payload for the same topic and command type was sent recently, we skip
re-sending within a TTL window.

Settings (from app.config.settings):
- mqtt_dedup_enabled (bool, default True)
- mqtt_dedup_ttl_seconds (int, default 60)
- mqtt_dedup_max_entries (int, default 1000)

Log markers:
- "mqtt.publisher.dedup enabled ..." at startup
- "MQTT dedup: skipping ..." when a publish is suppressed
"""

import asyncio
import json
import uuid
import time
import hashlib
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timezone

try:
    from aiomqtt import Client, MqttError
    AIOMQTT_AVAILABLE = True
except ImportError:
    AIOMQTT_AVAILABLE = False

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import DisplayClient

logger = get_logger(__name__)

class MqttSceneAssignmentService:
    """MQTT-based scene assignment service"""
    
    def __init__(self):
        self.broker_host = getattr(settings, 'mqtt_broker_host', 'localhost')
        self.broker_port = getattr(settings, 'mqtt_broker_port', 1883)
        self.client_id = f"mimir-scenes-{uuid.uuid4().hex[:8]}"

        self._pub = MQTTSceneAssignmentPublisher(client_id=self.client_id)
        
        # Client state
        self.client: Optional[Client] = None
        self.is_running = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

        # Deduplication cache (mirrors publisher behavior for this path)
        self._dedup_enabled: bool = bool(getattr(settings, "mqtt_dedup_enabled", True))
        self._dedup_ttl: int = int(getattr(settings, "mqtt_dedup_ttl_seconds", 60))
        self._dedup_max: int = int(getattr(settings, "mqtt_dedup_max_entries", 1000))
        # key -> (hash, ts)
        self._last_sent: Dict[str, Tuple[str, float]] = {}
        if self._dedup_enabled:
            logger.info(
                "mqtt.publisher.dedup enabled ttl=%ss max=%s (service path)",
                self._dedup_ttl,
                self._dedup_max,
            )
        
        logger.info(f"MQTT Scene Assignment Service initialized - Broker: {self.broker_host}:{self.broker_port}")
    
    async def start(self):
        """Start the MQTT scene assignment service"""
        if not AIOMQTT_AVAILABLE:
            logger.error("aiomqtt not available - MQTT scene assignment disabled")
            return False
        
        if self.is_running:
            logger.debug("MQTT scene assignment service already running")
            return True
        
        try:
            # Start the MQTT client task
            self.is_running = True
            
            # Start the queue worker task
            if self._worker_task is None:
                self._worker_task = asyncio.create_task(self._queue_worker())
            
            asyncio.create_task(self._mqtt_scene_loop())
            logger.info("MQTT scene assignment service started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MQTT scene assignment service: {e}")
            self.is_running = False
            return False
    
    async def stop(self):
        """Stop the MQTT scene assignment service"""
        self.is_running = False
        
        # Cancel worker task
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        
        # The client will be automatically disconnected when the context manager exits
        self.client = None
        logger.info("MQTT scene assignment service stopped")
        
    def is_connected(self) -> bool:
        return self._pub.is_connected()
    
    async def _mqtt_scene_loop(self) -> None:
        """Main MQTT scene assignment client loop with automatic reconnection.

        Maintains a persistent connection to the MQTT broker and processes device events.
        Logs connection attempts and errors with context for diagnostics.
        """
        while self.is_running:
            try:
                logger.info(
                    f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port} (client_id={self.client_id})"
                )
                async with Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    identifier=self.client_id,
                ) as client:
                    self.client = client
                    logger.info("MQTT scene assignment service connected - listening for device events")
                    self._pub._connected_evt.set()  # Mark as connected

                    # Subscribe to scene assignment acknowledgments and events
                    await client.subscribe("mimir/+/evt", qos=1)

                    # Message processing loop
                    async for message in client.messages:
                        await self._handle_device_event(message)

            except MqttError as e:
                logger.error(f"MQTT scene assignment connection error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in MQTT scene assignment loop: {e}")
            finally:
                self.client = None
                self._pub._connected_evt.clear()  # Mark as disconnected

            # Wait before reconnecting
            if self.is_running:
                logger.info("Reconnecting MQTT scene assignment service in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _handle_device_event(self, message):
        """Handle incoming MQTT device events"""
        try:
            topic_parts = message.topic.value.split('/')
            if len(topic_parts) < 3:
                return
            
            device_id = topic_parts[1]
            
            payload = json.loads(message.payload.decode())
            event_type = payload.get('event', 'unknown')
            
            logger.debug(f"Device {device_id} event: {event_type}")
            
            evt_type = payload.get("type")
            if evt_type == "ack":
                await self._handle_assignment_ack(device_id, payload)
            elif evt_type == "rendered":
                await self._handle_content_rendered(device_id, payload)
            elif evt_type == "error":
                await self._handle_device_error(device_id, payload)
                
        except Exception as e:
            logger.error(f"Error handling MQTT device event: {e}")
    
    async def _handle_assignment_ack(self, device_id: str, payload: Dict):
        """Handle scene assignment acknowledgment"""
        logger.info(f"Device {device_id} acknowledged scene assignment: {payload.get('scene_id')}")
        # Could update assignment status in database here
    
    async def _handle_content_rendered(self, device_id: str, payload: Dict):
        """Handle content rendered notification"""
        logger.info(f"Device {device_id} rendered content: {payload.get('content_id')}")
        # Could update render status in database here
    
    async def _handle_device_error(self, device_id: str, payload: Dict):
        """Handle device error reports"""
        error_msg = payload.get('message', 'Unknown error')
        logger.warning(f"Device {device_id} reported error: {error_msg}")

    async def _queue_worker(self):
        """Worker task to process queued MQTT messages"""
        while self.is_running:
            try:
                # Wait for messages in the queue
                topic, data, qos, retain = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                
                # Publish the message if connected
                if self.client and self.is_running:
                    await self.client.publish(topic, data, qos=qos, retain=retain)
                    logger.debug(f"Published MQTT message to {topic}")
                    
            except asyncio.TimeoutError:
                # Timeout is expected - keeps the loop responsive
                continue
            except Exception as e:
                logger.error(f"Error in MQTT queue worker: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying

    async def publish_command(self, target_id: str, payload: dict, qos: int = 1, retain: bool = False) -> bool:
        """
        Queue a command to publish to mimir/<target_id>/cmd.
        Safe to call anytime; will buffer until connected.
        """
        await self.start()  # lazy start if needed
        topic = f"mimir/{target_id}/cmd"
        try:
            # Deduplicate unchanged payloads (ignore volatile keys)
            if self._dedup_enabled and not self._should_publish(topic, payload):
                logger.debug("MQTT dedup (service): skipping unchanged payload for %s", topic)
                return True
            # Encode once, so the worker just publishes bytes
            data = json.dumps(payload).encode("utf-8")
            await self._queue.put((topic, data, qos, retain))
            logger.debug(f"Enqueued MQTT command -> {topic}: {payload}")
            return True
        except Exception as exc:
            logger.error(f"Failed to enqueue MQTT command for {topic}: {exc}")
            return False

    @staticmethod
    def _normalize_payload_for_hash(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of payload with volatile fields removed for stable hashing.

        Removes: timestamp, assignment_id, sequence. Applies recursively to lists/dicts.
        """
        volatile = {"timestamp", "assignment_id", "sequence"}

        def _strip(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _strip(v) for k, v in obj.items() if k not in volatile}
            if isinstance(obj, list):
                return [_strip(v) for v in obj]
            return obj

        return _strip(payload)

    def _payload_hash(self, payload: Dict[str, Any]) -> str:
        norm = self._normalize_payload_for_hash(payload)
        data = json.dumps(norm, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _should_publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Check dedup cache; record and return whether to publish now.

        Keyed by (topic, type) to scope by device and command type.
        """
        now = time.monotonic()
        # prune old entries
        if self._last_sent and (len(self._last_sent) > self._dedup_max):
            # drop oldest 10% when over limit
            sorted_items = sorted(self._last_sent.items(), key=lambda kv: kv[1][1])
            drop_n = max(1, len(self._last_sent) // 10)
            for k, _ in sorted_items[:drop_n]:
                self._last_sent.pop(k, None)

        # deterministic key per device/topic and command type
        cmd_type = str(payload.get("type", "?"))
        key = f"{topic}|{cmd_type}"
        h = self._payload_hash(payload)
        prev = self._last_sent.get(key)
        if prev:
            prev_hash, prev_ts = prev
            if prev_hash == h and (now - prev_ts) < self._dedup_ttl:
                return False  # skip
        self._last_sent[key] = (h, now)
        return True

    async def assign_scene_to_device(
        self, 
        device_id: str, 
        scene_id: str, 
        subchannel_id: Optional[str] = None,
        assignment_id: Optional[str] = None
    ) -> bool:
        """
        Assign a scene to a device via MQTT. This sets the scene assignment but does not
        send content. To display actual content, use send_display_image() with the image URL.
        
        Args:
            device_id: Target device identifier
            scene_id: Scene to assign
            subchannel_id: Optional subchannel identifier
            assignment_id: Optional assignment tracking ID, auto-generated if not provided
            
        Returns:
            bool: True if message was published successfully
        """
        # Generate assignment_id if not provided
        if assignment_id is None:
            assignment_id = f"set-{uuid.uuid4().hex[:8]}"
        
        payload = {
            "type": "set_scene",
            "scene_id": scene_id,  # Fixed: was incorrectly using scene_id as assignment_id
            "assignment_id": assignment_id,  # Fixed: now using proper assignment_id
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Only include subchannel_id if provided
        if subchannel_id is not None:
            payload["subchannel_id"] = subchannel_id
        
        return await self.publish_command(device_id, payload, qos=1, retain=False)
    
    async def refresh_device_content(
        self, 
        device_id: str,
        assignment_id: Optional[str] = None
    ) -> bool:
        """
        Send a refresh command to a device to trigger content update without scene reassignment.
        
        DEPRECATED: This method sends a generic refresh command but doesn't include actual content.
        The correct architecture is to use send_display_image() with the actual image URL instead.
        The display client will acknowledge refresh commands but waits for display_image commands.
        
        Args:
            device_id: Target device identifier
            assignment_id: Optional assignment tracking ID, auto-generated if not provided
            
        Returns:
            bool: True if message was published successfully
        """
        # Generate assignment_id if not provided
        if assignment_id is None:
            assignment_id = f"refresh-{uuid.uuid4().hex[:8]}"
        
        payload = {
            "type": "refresh",
            "assignment_id": assignment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        return await self.publish_command(device_id, payload, qos=1, retain=False)

    async def send_display_image(
        self,
        device_id: str,
        image_url: str,
        assignment_id: Optional[str] = None,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None,
        image_format: Optional[str] = None,
    ) -> bool:
        """
        Send a display_image command to a device with the actual image URL.
        This is the correct way to tell displays to show specific content.
        
        Args:
            device_id: Target device identifier
            image_url: Direct URL to the image to display
            assignment_id: Optional assignment tracking ID, auto-generated if not provided
            image_width: Optional image width hint
            image_height: Optional image height hint
            
        Returns:
            bool: True if message was published successfully
        """
        # Generate assignment_id if not provided
        if assignment_id is None:
            assignment_id = f"display-{uuid.uuid4().hex[:8]}"
        
        # Infer format if not explicitly provided
        fmt = (image_format or "").lower()
        if not fmt:
            lower_url = image_url.lower()
            for ext, candidate in [
                (".png", "png"),
                (".jpg", "jpeg"),
                (".jpeg", "jpeg"),
                (".gif", "gif"),
                (".webp", "webp"),
                (".bmp", "bmp"),
            ]:
                if lower_url.endswith(ext):
                    fmt = candidate
                    break
            if not fmt:
                # Simple magic prefix hint (base64/served copy) – leave unset if unknown
                if "scheduler_temp" in lower_url:
                    # default jpeg assumption for generated images
                    fmt = "jpeg"

        payload = {
            "type": "display_image",
            "image_url": image_url,
            "assignment_id": assignment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add optional image dimensions if provided
        if image_width is not None:
            payload["image_width"] = image_width
        if image_height is not None:
            payload["image_height"] = image_height
        if fmt:
            payload["image_format"] = fmt
        
        logger.debug(f"Sending display_image command to {device_id}")
        return await self.publish_command(device_id, payload, qos=1, retain=False)
      
    async def unassign_scene_from_device(self, device_id: str) -> bool:
        """Unassign scene from a device via MQTT"""
        try:
            if not self.client:
                logger.error("Cannot unassign scene - MQTT client not connected")
                return False
            
            # Update database
            db = SessionLocal()
            try:
                display = db.query(DisplayClient).filter(
                    DisplayClient.hostname == device_id
                ).first()
                
                if not display:
                    logger.error(f"Device {device_id} not found")
                    return False
                
                display.assigned_scene_id = None
                display.scene_assigned_at = None
                db.commit()
                
                # Send MQTT command to device
                command_topic = f"mimir/{device_id}/cmd"
                command_payload = {
                    "command": "unassign_scene",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                await self.client.publish(
                    command_topic, 
                    json.dumps(command_payload), 
                    qos=1
                )
                
                logger.info(f"Unassigned scene from device {device_id} via MQTT")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error unassigning scene via MQTT: {e}")
            return False

class MQTTSceneAssignmentPublisher:
    """
    Async MQTT publisher (singleton) for sending commands to displays.

    - Maintains a single background connection (aiomqtt)
    - Automatically reconnects
    - Uses an asyncio.Queue for backpressure / non-blocking publishing
    """

    _instance: Optional["MQTTSceneAssignmentPublisher"] = None

    def __init__(self, client_id: Optional[str] = None):
        if not AIOMQTT_AVAILABLE:
            raise RuntimeError("aiomqtt not available - install with `pip install aiomqtt`")

        self.broker_host = getattr(settings, 'mqtt_broker_host', 'localhost')
        self.broker_port = getattr(settings, 'mqtt_broker_port', 1883)
        self.client_id = client_id or f"mimir-pub-{uuid.uuid4().hex[:8]}"
        self._queue: "asyncio.Queue[Tuple[str, bytes, int, bool]]" = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._connected_evt = asyncio.Event()
        self._stopping = False
        self._client: Optional[Client] = None

        # Deduplication controls
        self._dedup_enabled: bool = bool(getattr(settings, "mqtt_dedup_enabled", True))
        self._dedup_ttl: int = int(getattr(settings, "mqtt_dedup_ttl_seconds", 60))
        self._dedup_max: int = int(getattr(settings, "mqtt_dedup_max_entries", 1000))
        # key -> (hash, ts)
        self._last_sent: Dict[str, Tuple[str, float]] = {}

    # ---------- Singleton helpers ----------
    @classmethod
    def initialize(cls, client_id: Optional[str] = None) -> "MQTTSceneAssignmentPublisher":
        """Create the singleton instance (idempotent)."""
        if cls._instance is None:
            cls._instance = cls(client_id)
        return cls._instance

    @classmethod
    def get(cls) -> "MQTTSceneAssignmentPublisher":
        """Return the singleton instance (must have been initialized)."""
        if cls._instance is None:
            raise RuntimeError("MQTTSceneAssignmentPublisher has not been initialized.")
        return cls._instance

    # ---------- Lifecycle ----------
    async def start(self) -> None:
        """Start the background publish loop (idempotent)."""
        if self._task and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="mqtt_publisher_loop")
        logger.info(f"MQTT publisher started for {self.broker_host}:{self.broker_port}")
        if self._dedup_enabled:
            logger.info(
                "mqtt.publisher.dedup enabled ttl=%ss max=%s (singleton)",
                self._dedup_ttl,
                self._dedup_max,
            )

    async def stop(self) -> None:
        """Stop the background loop and close the connection."""
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._connected_evt.clear()
        logger.info("MQTT publisher stopped")

    # ---------- Public API ----------
    async def publish_command(self, target_id: str, payload: dict, qos: int = 1, retain: bool = False) -> bool:
        """
        Queue a command to publish to mimir/<target_id>/cmd.
        Safe to call anytime; will buffer until connected.
        """
        await self.start()  # lazy start if needed
        topic = f"mimir/{target_id}/cmd"
        try:
            # Deduplicate unchanged payloads (ignore volatile keys)
            if self._dedup_enabled and not self._should_publish(topic, payload):
                logger.debug("MQTT dedup: skipping unchanged payload for %s", topic)
                return True
            # Encode once, so the worker just publishes bytes
            data = json.dumps(payload).encode("utf-8")
            await self._queue.put((topic, data, qos, retain))
            logger.debug(f"Enqueued MQTT command -> {topic}: {payload}")
            return True
        except Exception as exc:
            logger.error(f"Failed to enqueue MQTT command for {topic}: {exc}")
            return False

    # Convenience helper: send an "assign" command (matches your client expectations)
    async def assign_scene(
        self,
        device_id: str,
        scene_id: str,
        scene_name: str,
        content_url: str,
        *,
        etag: str = "v1",
        ttl_seconds: int = 3600,
        sequence: int = 1,
    ) -> bool:
        # Derive update_type / refresh_interval_s from scene database record if present
        update_type: Optional[str] = None
        refresh_interval_s: Optional[int] = None
        try:
            from app.db.base import SessionLocal as _SL  # local import to avoid circulars at module import
            from app.db.models import Scene as _Scene
            session = _SL()
            scene_obj = session.query(_Scene).filter(_Scene.id == scene_id).first()
            if scene_obj is not None:
                # Map DB field update_strategy (scheduler|push) to update_type (scheduled|push)
                strat = getattr(scene_obj, "update_strategy", None) or "scheduler"
                update_type = "push" if strat == "push" else "scheduled"
                if update_type == "scheduled":
                    refresh_interval_s = getattr(scene_obj, "push_fallback_poll_seconds", None)
                else:
                    refresh_interval_s = None
        except Exception as e:  # pragma: no cover - defensive
            logger.debug(f"Could not enrich assign payload with scene scheduling info: {e}")
        finally:
            try:
                session.close()  # type: ignore
            except Exception:
                pass

        payload = {
            "type": "assign",
            "assignment_id": f"mqtt-{uuid.uuid4().hex[:8]}",
            "sequence": sequence,
            "scene_id": scene_id,
            "scene_name": scene_name,
            "content": {
                "delivery": {
                    "type": "url",
                    "url": content_url,
                    "content_type": "image/png",
                    "etag": etag,
                    "ttl_seconds": ttl_seconds,
                },
                "metadata": {"caption": scene_name},
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if update_type:
            payload["update_type"] = update_type
        if update_type == "scheduled":
            payload["refresh_interval_s"] = refresh_interval_s
        return await self.publish_command(device_id, payload, qos=1, retain=False)

    # Convenience helper: clear stored scene on device
    async def clear_scene(self, device_id: str) -> bool:
        payload = {
            "type": "clear_scene",
            "assignment_id": f"mqtt-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.publish_command(device_id, payload, qos=1, retain=False)

    # Convenience helper: send display_image command with URL
    async def display_image(
        self,
        device_id: str,
        image_url: str,
        assignment_id: Optional[str] = None,
        image_width: Optional[int] = None,
        image_height: Optional[int] = None
    ) -> bool:
        """
        Send a display_image command to a device with the actual image URL.
        This follows the simple display architecture where displays just render URLs.
        
        Args:
            device_id: Target device identifier
            image_url: Direct URL to the image to display
            assignment_id: Optional assignment tracking ID, auto-generated if not provided
            image_width: Optional image width hint
            image_height: Optional image height hint
            
        Returns:
            bool: True if message was published successfully
        """
        if assignment_id is None:
            assignment_id = f"display-{uuid.uuid4().hex[:8]}"
            
        payload = {
            "type": "display_image",
            "image_url": image_url,
            "assignment_id": assignment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add optional image dimensions if provided
        if image_width is not None:
            payload["image_width"] = image_width
        if image_height is not None:
            payload["image_height"] = image_height
        
        logger.debug(f"Sending display_image command to {device_id}")
        return await self.publish_command(device_id, payload, qos=1, retain=False)

    # ---------- Worker / connection loop ----------
    async def _run(self) -> None:
        """Maintain a connection and flush the publish queue."""
        while not self._stopping:
            try:
                async with Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    identifier=self.client_id,
                ) as client:
                    self._client = client
                    self._connected_evt.set()
                    logger.info(f"MQTT publisher connected ({self.client_id})")

                    # Drain the queue; block when empty
                    while not self._stopping:
                        topic, data, qos, retain = await self._queue.get()
                        try:
                            await client.publish(topic, data, qos=qos, retain=retain)
                            logger.debug(f"Published MQTT -> {topic}")
                        except Exception as pub_exc:
                            logger.error(f"Publish failed for {topic}: {pub_exc}")
                            # If publish fails, requeue once to avoid message loss
                            try:
                                self._queue.put_nowait((topic, data, qos, retain))
                            except asyncio.QueueFull:
                                logger.warning("MQTT queue full; dropping message after publish error.")
                            # Break to reconnect
                            break
                        finally:
                            self._queue.task_done()

            except asyncio.CancelledError:
                break
            except MqttError as e:
                logger.error(f"MQTT publisher connection error: {e}")
            except Exception as e:
                logger.error(f"Unexpected MQTT publisher error: {e}")
            finally:
                self._connected_evt.clear()
                self._client = None

            if not self._stopping:
                logger.info("MQTT publisher reconnecting in 3s…")
                await asyncio.sleep(3)

    # ---------- Diagnostics ----------
    def is_connected(self) -> bool:
        return self._connected_evt.is_set()

    # ---------- Dedup helpers ----------
    @staticmethod
    def _normalize_payload_for_hash(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of payload with volatile fields removed for stable hashing.

        Removes: timestamp, assignment_id, sequence. Applies recursively to lists/dicts.
        """
        volatile = {"timestamp", "assignment_id", "sequence"}

        def _strip(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _strip(v) for k, v in obj.items() if k not in volatile}
            if isinstance(obj, list):
                return [_strip(v) for v in obj]
            return obj

        return _strip(payload)

    def _payload_hash(self, payload: Dict[str, Any]) -> str:
        norm = self._normalize_payload_for_hash(payload)
        data = json.dumps(norm, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _should_publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Check dedup cache; record and return whether to publish now.

        Keyed by (topic, type) to scope by device and command type.
        """
        now = time.monotonic()
        # prune old entries if too large
        if self._last_sent and (len(self._last_sent) > self._dedup_max):
            sorted_items = sorted(self._last_sent.items(), key=lambda kv: kv[1][1])
            drop_n = max(1, len(self._last_sent) // 10)
            for k, _ in sorted_items[:drop_n]:
                self._last_sent.pop(k, None)

        cmd_type = str(payload.get("type", "?"))
        key = f"{topic}|{cmd_type}"
        h = self._payload_hash(payload)
        prev = self._last_sent.get(key)
        if prev:
            prev_hash, prev_ts = prev
            if prev_hash == h and (now - prev_ts) < self._dedup_ttl:
                return False  # skip
        self._last_sent[key] = (h, now)
        return True

# Global service instance
mqtt_scene_service = MqttSceneAssignmentService()
mqtt_scene_assignment = MQTTSceneAssignmentPublisher()


async def setup_mqtt_scene_assignment():
    """Setup MQTT scene assignment service"""
    try:
        success = await mqtt_scene_service.start()
        
        if success:
            logger.info("MQTT scene assignment service setup completed")
        else:
            logger.warning("MQTT scene assignment service failed to start")
            
        return success
        
    except Exception as e:
        logger.error(f"Failed to setup MQTT scene assignment: {e}")
        return False
