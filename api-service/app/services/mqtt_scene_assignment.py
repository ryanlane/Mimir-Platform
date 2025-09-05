"""
MQTT Scene Assignment Service
Handles scene assignments via MQTT for pure MQTT communication workflow
"""
import asyncio
import json
import uuid
from typing import Dict, Optional
from datetime import datetime, timezone

try:
    from aiomqtt import Client, MqttError
    AIOMQTT_AVAILABLE = True
except ImportError:
    AIOMQTT_AVAILABLE = False

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import DisplayClient, Scene

logger = get_logger(__name__)


class MqttSceneAssignmentService:
    """MQTT-based scene assignment service"""
    
    def __init__(self):
        self.broker_host = getattr(settings, 'mqtt_broker_host', 'localhost')
        self.broker_port = getattr(settings, 'mqtt_broker_port', 1883)
        self.client_id = f"mimir-scenes-{uuid.uuid4().hex[:8]}"
        
        # Client state
        self.client: Optional[Client] = None
        self.is_running = False
        
        logger.info(f"MQTT Scene Assignment Service initialized - Broker: {self.broker_host}:{self.broker_port}")
    
    async def start(self):
        """Start the MQTT scene assignment service"""
        if not AIOMQTT_AVAILABLE:
            logger.error("aiomqtt not available - MQTT scene assignment disabled")
            return False
        
        if self.is_running:
            logger.warning("MQTT scene assignment service already running")
            return True
        
        try:
            # Start the MQTT client task
            self.is_running = True
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
        # The client will be automatically disconnected when the context manager exits
        self.client = None
        logger.info("MQTT scene assignment service stopped")
        
    def is_connected(self) -> bool:
        return self._pub.is_connected()
    
    async def _mqtt_scene_loop(self):
        """Main MQTT scene assignment client loop with automatic reconnection"""
        while self.is_running:
            try:
                async with Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    identifier=self.client_id,
                ) as client:
                    self.client = client
                    
                    # Subscribe to scene assignment acknowledgments and events
                    await client.subscribe("mimir/+/evt", qos=1)
                    
                    logger.info("MQTT scene assignment service connected - listening for device events")
                    
                    # Message processing loop
                    async for message in client.messages:
                        await self._handle_device_event(message)
                        
            except MqttError as e:
                logger.error(f"MQTT scene assignment connection error: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error in MQTT scene assignment loop: {e}")
                
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
    
    async def assign_scene_to_device(self, device_id: str, scene_id: str) -> bool:
        """Assign a scene to a device via MQTT."""
        try:
            if not self.client:
                logger.error("Cannot assign scene - MQTT client not connected")
                return False

            db = SessionLocal()
            try:
                scene = db.query(Scene).filter(Scene.id == scene_id).first()
                if not scene:
                    logger.error(f"Scene {scene_id} not found")
                    return False

                # Resolve device row; prefer an active MQTT id if you store it.
                display = db.query(DisplayClient).filter(
                    (DisplayClient.hostname == device_id) | (DisplayClient.mqtt_id == device_id)
                ).first()
                if not display:
                    logger.error(f"Device {device_id} not found")
                    return False

                # Decide which id to publish to (active MQTT id if available)
                topic_id = getattr(display, "mqtt_id", None) or display.hostname or device_id
                command_topic = f"mimir/{topic_id}/cmd"

                # Persist assignment metadata
                display.assigned_scene_id = scene_id
                display.scene_assigned_at = datetime.now(timezone.utc)
                db.commit()

                # Build content URL using your API settings
                api_base_url = f"http://{settings.api_host}:{settings.api_port}"
                content_url = f"{api_base_url}/api/scenes/{scene_id}/content"

                payload = {
                    "type": "assign",
                    "assignment_id": f"mqtt-{uuid.uuid4().hex[:8]}",
                    "sequence": 1,
                    "scene_id": scene_id,
                    "scene_name": scene.name,
                    # You can omit 'display' if you don't need to override client defaults:
                    # "display": {"resolution": {"width": 800, "height": 480}},
                    "content": {
                        "delivery": {
                            "type": "url",
                            "url": content_url,
                            "content_type": "image/png",
                            "etag": "v1",
                            "ttl_seconds": 3600
                        },
                        "metadata": {"caption": scene.name}
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

                # Publish the command (QoS 1; retain False)
                await self.client.publish(command_topic, json.dumps(payload), qos=1)
                logger.info(f"Assigned scene {scene_id} to device {topic_id} via MQTT ({command_topic})")
                return True

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error assigning scene via MQTT: {e}", exc_info=True)
            return False

    
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

    def __init__(self, broker_host: str, broker_port: int = 1883, client_id: Optional[str] = None):
        if not AIOMQTT_AVAILABLE:
            raise RuntimeError("aiomqtt not available - install with `pip install aiomqtt`")

        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id or f"mimir-pub-{uuid.uuid4().hex[:8]}"
        self._queue: "asyncio.Queue[Tuple[str, bytes, int, bool]]" = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._connected_evt = asyncio.Event()
        self._stopping = False
        self._client: Optional[Client] = None

    # ---------- Singleton helpers ----------
    @classmethod
    def initialize(cls, broker_host: str, broker_port: int = 1883, client_id: Optional[str] = None) -> "MQTTSceneAssignmentPublisher":
        """Create the singleton instance (idempotent)."""
        if cls._instance is None:
            cls._instance = cls(broker_host, broker_port, client_id)
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
        return await self.publish_command(device_id, payload, qos=1, retain=False)

    # Convenience helper: clear stored scene on device
    async def clear_scene(self, device_id: str) -> bool:
        payload = {
            "type": "clear_scene",
            "assignment_id": f"mqtt-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
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

# Global service instance
mqtt_scene_service = MqttSceneAssignmentService()


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
