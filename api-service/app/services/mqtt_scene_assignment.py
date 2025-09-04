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

from sqlalchemy.orm import Session
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
        """Assign a scene to a device via MQTT"""
        try:
            if not self.client:
                logger.error("Cannot assign scene - MQTT client not connected")
                return False
            
            # Get scene details from database
            db = SessionLocal()
            try:
                scene = db.query(Scene).filter(Scene.id == scene_id).first()
                if not scene:
                    logger.error(f"Scene {scene_id} not found")
                    return False
                
                # Update display client assignment in database
                display = db.query(DisplayClient).filter(
                    DisplayClient.hostname == device_id
                ).first()
                
                if not display:
                    logger.error(f"Device {device_id} not found")
                    return False
                
                display.assigned_scene_id = scene_id
                display.scene_assigned_at = datetime.now(timezone.utc)
                db.commit()
                
                # Send MQTT command to device
                command_topic = f"mimir/{device_id}/cmd"
                
                # Build content URL using the configured API settings
                api_base_url = f"http://{settings.api_host}:{settings.api_port}"
                content_url = f"{api_base_url}/api/scenes/{scene_id}/content"
                
                payload = {
                    "type": "assign",
                    "assignment_id": f"mqtt-{uuid.uuid4().hex[:8]}",
                    "scene_id": scene_id,
                    "scene_name": scene.name,
                    "content": {"url": content_url},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                
                # simplest: ask the device to refresh (your client currently acks refresh)
                await self.client.publish(f"mimir/{device_id}/cmd",
                    json.dumps({"type":"refresh","timestamp":datetime.now(timezone.utc).isoformat()}),
                    qos=1
                )
                                
                logger.info(f"Assigned scene {scene_id} to device {device_id} via MQTT")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error assigning scene via MQTT: {e}")
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
