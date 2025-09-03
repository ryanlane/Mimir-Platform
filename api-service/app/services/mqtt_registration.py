"""
MQTT Registration Service
Handles device registration requests via MQTT
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.core.logging import get_logger
from app.db.models import DisplayClient
from app.db.base import SessionLocal
from app.config import settings

try:
    import aiomqtt
except ImportError:
    aiomqtt = None


def get_db():
    """Database dependency"""
    return SessionLocal()

db = get_db()  

logger = get_logger(__name__)

class MqttRegistrationService:
    def __init__(self):
        self.client: Optional[aiomqtt.Client] = None
        self.running = False

    async def start(self):
        """Start the MQTT registration service"""
        if not settings.mqtt_enabled or not aiomqtt:
            logger.info("MQTT registration service disabled or aiomqtt not available")
            return
            
        try:
            self.client = aiomqtt.Client(
                hostname=settings.mqtt_broker_host,
                port=settings.mqtt_broker_port,
                identifier="mimir-registration-service"
            )
            
            self.running = True
            await self._connect_and_listen()
            
        except Exception as e:
            logger.error(f"Failed to start MQTT registration service: {e}")

    async def stop(self):
        """Stop the MQTT registration service"""
        self.running = False
        if self.client:
            await self.client.disconnect()

    async def _connect_and_listen(self):
        """Connect to MQTT broker and listen for registration requests"""
        try:
            await self.client.connect()
            logger.info("MQTT registration service connected")
            
            # Subscribe to registration requests
            await self.client.subscribe("mimir/registry/register")
            logger.info("Subscribed to mimir/registry/register")
            
            async for message in self.client.messages:
                if not self.running:
                    break
                    
                try:
                    await self._handle_registration_request(message)
                except Exception as e:
                    logger.error(f"Error handling registration request: {e}")
                    
        except Exception as e:
            logger.error(f"MQTT registration service error: {e}")

    async def _handle_registration_request(self, message):
        """Handle a registration request from a display"""
        try:
            # Parse the registration request
            request_data = json.loads(message.payload.decode())
            device_id = request_data.get("device_id")
            reply_to = request_data.get("reply_to")
            capabilities = request_data.get("capabilities", {})
            metadata = request_data.get("metadata", {})
            
            logger.info(f"Processing registration request for device: {device_id}")
            
            # Create or update the display client in database
            db = next(get_db())
            try:
                # Check if display already exists
                existing_display = db.query(DisplayClient).filter(
                    DisplayClient.hostname == metadata.get("hostname", device_id)
                ).first()
                
                if existing_display:
                    # Update existing display
                    existing_display.name = metadata.get("name", "Unknown Display")
                    existing_display.location = metadata.get("location", "Unknown")
                    existing_display.is_online = True
                    existing_display.last_seen = datetime.now(timezone.utc)
                    existing_display.client_version = metadata.get("client_version", "unknown")
                    existing_display.resolution = capabilities.get("resolution", [800, 480])
                    existing_display.orientation = capabilities.get("orientation", "landscape")
                    existing_display.refresh_rate_hz = capabilities.get("refresh_rate_hz", 1)
                    existing_display.tags = metadata.get("tags", [])
                    
                    db.commit()
                    assigned_id = existing_display.id
                    logger.info(f"Updated existing display: {assigned_id}")
                    
                else:
                    # Create new display
                    new_display = DisplayClient(
                        name=metadata.get("name", "Unknown Display"),
                        description=metadata.get("description", "MQTT registered display"),
                        location=metadata.get("location", "Unknown"),
                        hostname=metadata.get("hostname", device_id),
                        is_online=True,
                        last_seen=datetime.now(timezone.utc),
                        client_version=metadata.get("client_version", "unknown"),
                        resolution=capabilities.get("resolution", [800, 480]),
                        orientation=capabilities.get("orientation", "landscape"),
                        refresh_rate_hz=capabilities.get("refresh_rate_hz", 1),
                        tags=metadata.get("tags", [])
                    )
                    
                    db.add(new_display)
                    db.commit()
                    db.refresh(new_display)
                    assigned_id = new_display.id
                    logger.info(f"Created new display: {assigned_id}")
                
                # Send success response
                response = {
                    "success": True,
                    "assigned_id": str(assigned_id),
                    "device_id": device_id,
                    "message": "Registration successful",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database error during registration: {e}")
                
                # Send error response
                response = {
                    "success": False,
                    "error": f"Registration failed: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            finally:
                db.close()
            
            # Send response back to the device
            if reply_to and self.client:
                await self.client.publish(
                    reply_to,
                    json.dumps(response)
                )
                logger.info(f"Sent registration response to {reply_to}")
                
        except Exception as e:
            logger.error(f"Error processing registration request: {e}")

# Global service instance
mqtt_registration_service = MqttRegistrationService()

async def setup_mqtt_registration():
    """Setup the MQTT registration service"""
    await mqtt_registration_service.start()

async def cleanup_mqtt_registration():
    """Cleanup the MQTT registration service"""
    await mqtt_registration_service.stop()