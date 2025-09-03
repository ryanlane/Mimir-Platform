"""
MQTT Registration Service
Handles device registration requests via MQTT
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any

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

class AutoRegistrationService:
    def __init__(self):
        self.mqtt_client = None
        self.running = False

    async def start(self):
        """Start the auto-registration service with MQTT client"""
        if not settings.mqtt_enabled or not aiomqtt:
            logger.info("Auto-registration service disabled (MQTT not available)")
            return
            
        try:
            self.mqtt_client = aiomqtt.Client(
                hostname=settings.mqtt_broker_host,
                port=settings.mqtt_broker_port,
                identifier="mimir-auto-registration"
            )
            await self.mqtt_client.connect()
            self.running = True
            logger.info("Auto-registration MQTT service started")
            
            # Start listening for acknowledgments
            asyncio.create_task(self._listen_for_acks())
            
        except Exception as e:
            logger.error(f"Failed to start auto-registration MQTT service: {e}")

    async def stop(self):
        """Stop the auto-registration service"""
        self.running = False
        if self.mqtt_client:
            await self.mqtt_client.disconnect()

    async def handle_discovered_display(self, display_info: Dict[str, Any]):
        """
        Handle a newly discovered display via mDNS
        
        Flow:
        1. Check if display is already registered
        2a. If registered: Send "ready" acknowledgment via MQTT
        2b. If not registered: Send registration request via MQTT
        """
        hostname = display_info.get('hostname')
        display_id = display_info.get('display_id')
        
        if not hostname or not self.mqtt_client:
            return
            
        logger.info(f"Processing discovered display: {hostname} ({display_id})")
        
        # Check if display is already registered
        db = SessionLocal()
        try:
            existing_display = db.query(DisplayClient).filter(
                DisplayClient.hostname == hostname
            ).first()
            
            if existing_display:
                # Display is already registered - send ready acknowledgment
                await self._send_ready_acknowledgment(hostname, existing_display.id)
            else:
                # Display not registered - request registration details
                await self._request_registration_details(hostname, display_info)
                
        except Exception as e:
            logger.error(f"Database error checking display registration: {e}")
        finally:
            db.close()

    async def _send_ready_acknowledgment(self, hostname: str, display_id: str):
        """Send ready acknowledgment to an already registered display"""
        try:
            message = {
                "action": "ready",
                "message": "Display is registered and ready for commands",
                "display_id": str(display_id),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            topic = f"mimir/{hostname}/cmd"
            await self.mqtt_client.publish(topic, json.dumps(message))
            logger.info(f"Sent ready acknowledgment to {hostname}")
            
        except Exception as e:
            logger.error(f"Failed to send ready acknowledgment to {hostname}: {e}")

    async def _request_registration_details(self, hostname: str, display_info: Dict[str, Any]):
        """Request registration details from an unregistered display"""
        try:
            message = {
                "action": "register",
                "message": "Please provide registration details",
                "reply_to": f"mimir/{hostname}/registration/reply",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            topic = f"mimir/{hostname}/cmd"
            await self.mqtt_client.publish(topic, json.dumps(message))
            logger.info(f"Sent registration request to {hostname}")
            
        except Exception as e:
            logger.error(f"Failed to send registration request to {hostname}: {e}")

    async def _listen_for_acks(self):
        """Listen for acknowledgment responses from displays"""
        try:
            await self.mqtt_client.subscribe("mimir/+/ack")
            await self.mqtt_client.subscribe("mimir/+/registration/reply")
            
            async for message in self.mqtt_client.messages:
                if not self.running:
                    break
                    
                try:
                    await self._handle_display_response(message)
                except Exception as e:
                    logger.error(f"Error handling display response: {e}")
                    
        except Exception as e:
            logger.error(f"Error listening for display acknowledgments: {e}")

    async def _handle_display_response(self, message):
        """Handle responses from displays"""
        try:
            topic_parts = message.topic.value.split('/')
            if len(topic_parts) < 3:
                return
                
            hostname = topic_parts[1]
            response_type = topic_parts[2]
            
            data = json.loads(message.payload.decode())
            
            if response_type == "ack":
                logger.info(f"Received acknowledgment from {hostname}: {data.get('message', 'OK')}")
                
            elif response_type == "registration" and len(topic_parts) > 3 and topic_parts[3] == "reply":
                await self._process_registration_reply(hostname, data)
                
        except Exception as e:
            logger.error(f"Error processing display response: {e}")

    async def _process_registration_reply(self, hostname: str, registration_data: Dict[str, Any]):
        """Process registration details from a display and create database entry"""
        try:
            capabilities = registration_data.get("capabilities", {})
            metadata = registration_data.get("metadata", {})
            
            # Create new display in database
            db = SessionLocal()
            try:
                new_display = DisplayClient(
                    name=metadata.get("name", f"Display {hostname}"),
                    description=metadata.get("description", "Auto-registered display"),
                    location=metadata.get("location", "Unknown"),
                    hostname=hostname,
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
                
                logger.info(f"Registered new display: {hostname} (ID: {new_display.id})")
                
                # Send confirmation back to display
                await self._send_registration_confirmation(hostname, new_display.id)
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database error creating display: {e}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing registration reply from {hostname}: {e}")

    async def _send_registration_confirmation(self, hostname: str, display_id: str):
        """Send registration confirmation to newly registered display"""
        try:
            message = {
                "action": "registration_complete",
                "display_id": str(display_id),
                "message": "Registration successful, ready for commands",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            topic = f"mimir/{hostname}/cmd"
            await self.mqtt_client.publish(topic, json.dumps(message))
            logger.info(f"Sent registration confirmation to {hostname}")
            
        except Exception as e:
            logger.error(f"Failed to send registration confirmation to {hostname}: {e}")

# Global service instance
auto_registration_service = AutoRegistrationService()

async def setup_auto_registration():
    """Setup the auto-registration service"""
    await auto_registration_service.start()

async def cleanup_auto_registration():
    """Cleanup the auto-registration service"""
    await auto_registration_service.stop()