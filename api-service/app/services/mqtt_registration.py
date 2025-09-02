"""
MQTT Registration Service
Handles device registration via MQTT for pure MQTT communication workflow
"""
import asyncio
import json
import uuid
from typing import Dict, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager

try:
    from aiomqtt import Client, MqttError
    AIOMQTT_AVAILABLE = True
except ImportError:
    AIOMQTT_AVAILABLE = False

from sqlalchemy.orm import Session
from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.models.display_client import DisplayClient
from app.models.display_client_status import DisplayClientStatus

logger = get_logger(__name__)


class MqttRegistrationService:
    """MQTT-based device registration service"""
    
    def __init__(self):
        self.broker_host = getattr(settings, 'mqtt_broker_host', 'localhost')
        self.broker_port = getattr(settings, 'mqtt_broker_port', 1883)
        self.client_id = f"mimir-registration-{uuid.uuid4().hex[:8]}"
        
        # Client state
        self.client: Optional[Client] = None
        self.is_running = False
        
        logger.info(f"MQTT Registration Service initialized - Broker: {self.broker_host}:{self.broker_port}")
    
    async def start(self):
        """Start the MQTT registration service"""
        if not AIOMQTT_AVAILABLE:
            logger.error("aiomqtt not available - MQTT registration disabled")
            return False
        
        if self.is_running:
            logger.warning("MQTT registration service already running")
            return True
        
        try:
            # Start the MQTT client task
            self.is_running = True
            asyncio.create_task(self._mqtt_registration_loop())
            logger.info("MQTT registration service started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MQTT registration service: {e}")
            self.is_running = False
            return False
    
    async def stop(self):
        """Stop the MQTT registration service"""
        self.is_running = False
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting MQTT registration client: {e}")
        logger.info("MQTT registration service stopped")
    
    async def _mqtt_registration_loop(self):
        """Main MQTT registration client loop with automatic reconnection"""
        while self.is_running:
            try:
                async with Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    identifier=self.client_id,
                ) as client:
                    self.client = client
                    
                    # Subscribe to registration requests
                    await client.subscribe("mimir/registry/register", qos=1)
                    
                    logger.info("MQTT registration service connected - listening for registrations")
                    
                    # Message processing loop
                    async for message in client.messages:
                        await self._handle_registration_request(message)
                        
            except MqttError as e:
                logger.error(f"MQTT registration connection error: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error in MQTT registration loop: {e}")
                
            # Wait before reconnecting
            if self.is_running:
                logger.info("Reconnecting MQTT registration service in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _handle_registration_request(self, message):
        """Handle incoming MQTT registration requests"""
        try:
            payload = json.loads(message.payload.decode())
            logger.info(f"Received MQTT registration request: {payload.get('device_id', 'unknown')}")
            
            # Validate required fields
            device_id = payload.get('device_id')
            capabilities = payload.get('capabilities', {})
            metadata = payload.get('metadata', {})
            reply_to = payload.get('reply_to')
            
            if not device_id:
                logger.error("Registration request missing device_id")
                return
            
            if not reply_to:
                logger.error("Registration request missing reply_to topic")
                return
            
            # Process the registration
            response = await self._process_registration(device_id, capabilities, metadata)
            
            # Send response back to device
            await self._send_registration_response(reply_to, response)
            
        except Exception as e:
            logger.error(f"Error handling MQTT registration request: {e}")
    
    async def _process_registration(self, device_id: str, capabilities: Dict, metadata: Dict) -> Dict:
        """Process the device registration and update database"""
        try:
            db = SessionLocal()
            
            try:
                # Check if device already exists
                existing_device = db.query(DisplayClient).filter(
                    DisplayClient.hostname == device_id
                ).first()
                
                if existing_device:
                    # Update existing device
                    display_client = existing_device
                    logger.info(f"Updating existing device: {device_id}")
                else:
                    # Create new device
                    display_client = DisplayClient()
                    logger.info(f"Creating new device: {device_id}")
                
                # Update device properties
                display_client.hostname = device_id
                display_client.display_name = metadata.get('name', f'MQTT Device {device_id}')
                display_client.display_location = metadata.get('location', 'Unknown')
                display_client.client_version = metadata.get('client_version', '1.0.0')
                display_client.capabilities = capabilities
                display_client.metadata = metadata
                display_client.communication_method = 'mqtt'
                display_client.last_seen = datetime.now(timezone.utc)
                display_client.discovery_method = 'mqtt_registration'
                
                # Handle tags
                tags = metadata.get('tags', [])
                if isinstance(tags, list):
                    display_client.tags = ','.join(tags) if tags else ''
                else:
                    display_client.tags = str(tags)
                
                # Save to database
                if not existing_device:
                    db.add(display_client)
                
                db.commit()
                db.refresh(display_client)
                
                # Update status
                status = db.query(DisplayClientStatus).filter(
                    DisplayClientStatus.display_client_id == display_client.id
                ).first()
                
                if not status:
                    status = DisplayClientStatus(
                        display_client_id=display_client.id,
                        online=True,
                        last_seen=datetime.now(timezone.utc),
                        communication_method='mqtt'
                    )
                    db.add(status)
                else:
                    status.online = True
                    status.last_seen = datetime.now(timezone.utc)
                    status.communication_method = 'mqtt'
                
                db.commit()
                
                # Prepare success response
                response = {
                    "success": True,
                    "assigned_id": device_id,  # Keep the same ID
                    "display_id": display_client.id,
                    "message": "Device registered successfully via MQTT",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "capabilities": capabilities,
                    "communication_method": "mqtt"
                }
                
                logger.info(f"Successfully registered device {device_id} (DB ID: {display_client.id})")
                return response
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Database error during registration: {e}")
            return {
                "success": False,
                "error": f"Registration failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _send_registration_response(self, reply_to: str, response: Dict):
        """Send registration response back to the device"""
        try:
            if not self.client:
                logger.error("Cannot send registration response - MQTT client not connected")
                return
            
            payload = json.dumps(response)
            await self.client.publish(reply_to, payload, qos=1)
            
            if response.get("success"):
                logger.info(f"Sent successful registration response to {reply_to}")
            else:
                logger.error(f"Sent error registration response to {reply_to}: {response.get('error')}")
                
        except Exception as e:
            logger.error(f"Error sending registration response: {e}")


# Global service instance
mqtt_registration_service = MqttRegistrationService()


async def setup_mqtt_registration():
    """Setup MQTT registration service"""
    try:
        success = await mqtt_registration_service.start()
        
        if success:
            logger.info("MQTT registration service setup completed")
        else:
            logger.warning("MQTT registration service failed to start")
            
        return success
        
    except Exception as e:
        logger.error(f"Failed to setup MQTT registration: {e}")
        return False
