"""
Auto-Registration Service
Simple workflow: mDNS discovery → check registration → MQTT registration request → send test image
"""
import asyncio
import json
import time
import uuid
from typing import Optional
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
from app.db.models import DisplayClient
from app.services.mdns_discovery import mdns_discovery_service, DiscoveredDisplay

logger = get_logger(__name__)


class AutoRegistrationService:
    """Simple auto-registration workflow triggered by mDNS discovery"""
    
    def __init__(self):
        self.mqtt_client: Optional[Client] = None
        self.is_running = False
        
    async def start(self):
        """Start the auto-registration service"""
        if not AIOMQTT_AVAILABLE:
            logger.warning("MQTT not available - auto-registration disabled")
            return False
            
        # Add callback to mDNS discovery
        mdns_discovery_service.add_discovery_callback(self._on_display_discovered)
        self.is_running = True
        
        # Start MQTT client for sending registration requests
        asyncio.create_task(self._mqtt_client_loop())
        
        logger.info("Auto-registration service started")
        return True
    
    async def stop(self):
        """Stop the auto-registration service"""
        if self.is_running:
            mdns_discovery_service.remove_discovery_callback(self._on_display_discovered)
            self.is_running = False
            
            if self.mqtt_client:
                try:
                    await self.mqtt_client.disconnect()
                except:
                    pass
                    
        logger.info("Auto-registration service stopped")
    
    async def _mqtt_client_loop(self):
        """Maintain MQTT connection for sending registration requests"""
        while self.is_running:
            try:
                async with Client(
                    hostname=getattr(settings, 'mqtt_broker_host', 'localhost'),
                    port=getattr(settings, 'mqtt_broker_port', 1883),
                    identifier=f"auto-registration-{uuid.uuid4().hex[:8]}"
                ) as client:
                    self.mqtt_client = client
                    logger.info("Auto-registration MQTT client connected")
                    
                    # Just keep the connection alive
                    while self.is_running:
                        await asyncio.sleep(10)
                        
            except Exception as e:
                logger.error(f"Auto-registration MQTT error: {e}")
                if self.is_running:
                    await asyncio.sleep(5)
    
    def _on_display_discovered(self, display: DiscoveredDisplay, event_type: str):
        """Handle mDNS discovery events"""
        if event_type == "discovered":
            # Check if this display is registered
            if not self._is_display_registered(display):
                logger.info(f"New unregistered display discovered: {display.hostname} (display_id: {display.display_id})")
                # Send MQTT registration request
                asyncio.create_task(self._request_registration(display))
    
    def _is_display_registered(self, display: DiscoveredDisplay) -> bool:
        """Check if display is already registered in database"""
        try:
            db = SessionLocal()
            try:
                # Check by hostname, not display_id (which may have prefixes)
                existing = db.query(DisplayClient).filter(
                    DisplayClient.hostname == display.hostname
                ).first()
                return existing is not None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error checking registration for {display.hostname}: {e}")
            return False
    
    async def _request_registration(self, display: DiscoveredDisplay):
        """Send MQTT registration request to display"""
        try:
            if not self.mqtt_client:
                logger.error("Cannot send registration request - MQTT not connected")
                return
            
            # Simple registration request
            request = {
                "type": "register",
                "action": "register",
                "api_endpoint": f"http://{settings.api_host}:{settings.api_port}",
                "mqtt_broker": f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "assignment_id": f"reg-{display.hostname}-{int(time.time())}"
            }
            
            # Send to display's command topic (use hostname, not display_id)
            topic = f"mimir/{display.hostname}/cmd"
            await self.mqtt_client.publish(topic, json.dumps(request), qos=1)
            
            logger.info(f"Sent registration request to {display.hostname}")
            
            # Schedule test image after a delay
            asyncio.create_task(self._send_test_image_delayed(display.hostname))
            
        except Exception as e:
            logger.error(f"Error sending registration request to {display.display_id}: {e}")
    
    async def _send_test_image_delayed(self, hostname: str):
        """Send a test image after registration"""
        try:
            # Wait for registration to complete
            await asyncio.sleep(5)
            
            if not self.mqtt_client:
                return
            
            # Send simple test image URL
            test_image = {
                "type": "display_image",
                "action": "display_image",
                "image_url": f"http://{settings.api_host}:{settings.api_port}/static/test-success.html",
                "message": "Registration Successful!",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "assignment_id": f"img-{hostname}-{int(time.time())}"
            }
            
            topic = f"mimir/{hostname}/cmd"
            await self.mqtt_client.publish(topic, json.dumps(test_image), qos=1)
            
            logger.info(f"Sent test image to {hostname}")
            
        except Exception as e:
            logger.error(f"Error sending test image to {hostname}: {e}")


# Global service instance
auto_registration_service = AutoRegistrationService()


async def setup_auto_registration():
    """Setup auto-registration service"""
    try:
        success = await auto_registration_service.start()
        return success
    except Exception as e:
        logger.error(f"Failed to setup auto-registration: {e}")
        return False
