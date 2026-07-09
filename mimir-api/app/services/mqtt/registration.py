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
MQTT Registration Service
Handles device registration requests via MQTT
"""
import asyncio
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import DisplayClient

if TYPE_CHECKING:
    from app.services.mdns_discovery import DiscoveredDisplay

try:
    import aiomqtt
except ImportError:
    aiomqtt = None


def get_db():
    """Database dependency"""
    return SessionLocal()

db = get_db()

logger = get_logger(__name__)

# TODO: This class is currently unused/dead code. It is never instantiated
# with .start() anywhere in the app (not even in main.py), and as of the
# pairing/provisioning finalize-command fix it has no remaining callers at
# all -- routes now send finalize_registration via the already-running
# MQTTSceneAssignmentPublisher singleton instead. Either wire this listener
# up properly (start() + its mimir/+/evt / mimir/+/registration/reply
# subscriptions) or remove it; revisit before relying on auto-registration
# beyond the pairing-code/provisioning-bundle flows.
class AutoRegistrationService:
    def __init__(self):
        self.mqtt_client = None
        self.running = False
        # Topics
        self._registry_topics = [
            "mimir/registry/register",          # legacy path (temporary)
            "mimir/registry/v1/register",       # versioned path
        ]

    async def start(self):
        """Start the auto-registration service with MQTT client"""
        if not settings.mqtt_enabled or not aiomqtt:
            logger.info("Auto-registration service disabled (MQTT not available)")
            return False

        try:
            self.running = True
            # Start the MQTT listening task
            asyncio.create_task(self._run_mqtt_client())
            logger.info("Auto-registration MQTT service started")
            return True

        except Exception as e:
            logger.error(f"Failed to start auto-registration MQTT service: {e}")
            return False

    async def _run_mqtt_client(self):
        """Run the MQTT client in a loop"""
        while self.running:
            try:
                async with aiomqtt.Client(
                    hostname=settings.mqtt_broker_host,
                    port=settings.mqtt_broker_port,
                    identifier="mimir-auto-registration"
                ) as client:
                    self.mqtt_client = client
                    await self._listen_for_acks()
            except Exception as e:
                logger.error(f"MQTT client error in auto-registration: {e}")
                if self.running:
                    await asyncio.sleep(5)  # Wait before reconnecting

    async def stop(self):
        """Stop the auto-registration service"""
        self.running = False
        if self.mqtt_client:
            # The client will be automatically disconnected when the context manager exits
            self.mqtt_client = None

    async def handle_discovered_display(self, display: 'DiscoveredDisplay', event: str):
        """
        Handle a newly discovered display via mDNS

        Flow:
        1. Check if display is already registered
        2a. If registered: Send "ready" acknowledgment via MQTT
        2b. If not registered: Send registration request via MQTT
        """
        # Only handle discovery events, not loss events
        if event != "discovered":
            return

        hostname = display.hostname
        display_id = display.device_id

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
                await self._request_registration_details(hostname, display)

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

    async def _request_registration_details(self, hostname: str, display: 'DiscoveredDisplay'):
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
            # Presence / event / legacy flows
            await self.mqtt_client.subscribe("mimir/+/evt")
            await self.mqtt_client.subscribe("mimir/+/registration/reply")
            # New proactive registration channels
            for t in self._registry_topics:
                await self.mqtt_client.subscribe(t)

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
        full_topic = message.topic.value
        payload_raw = message.payload.decode()
        topic_parts = full_topic.split('/')
        data: dict[str, object]
        try:
            data = json.loads(payload_raw)
        except json.JSONDecodeError:
            logger.warning("Non-JSON payload on %s", full_topic)
            return

        # Registration bus (new proactive)
        if full_topic in self._registry_topics:
            await self._handle_registry_request(data, full_topic)
            return

        # Per-device channels (legacy / reply / events)
        if len(topic_parts) < 3:
            return
        device_id = topic_parts[1]
        channel = topic_parts[2]

        if channel == "evt":
            if data.get("type") == "ack":
                logger.info(f"ACK from {device_id}: {data}")
        elif channel == "registration" and len(topic_parts) > 3 and topic_parts[3] == "reply":
            await self._process_registration_reply(device_id, data)

    # -------- New proactive registration flow --------
    async def _handle_registry_request(self, data: dict[str, object], topic: str):
        """Process a proactive registration frame from a device.

        Expected shape:
          device_id: str
          capabilities: {...}
          metadata: {...}
          reply_to: mqtt topic for reply
          timestamp: client supplied (optional)
        """
        device_id = data.get("device_id")
        reply_to = data.get("reply_to")
        if not device_id or not reply_to:
            logger.warning("Malformed registration payload (missing device_id or reply_to) topic=%s data=%s", topic, data)
            return

        capabilities = data.get("capabilities") or {}
        metadata = data.get("metadata") or {}
        resolution = capabilities.get("resolution") or capabilities.get("native_resolution") or [800, 480]
        orientation = capabilities.get("orientation", "landscape")
        client_version = metadata.get("client_version", "unknown")
        hostname = metadata.get("hostname") or device_id

        # Upsert DB row idempotently (match on hostname OR device_id stored in hostname field for now)
        db = SessionLocal()
        created = False
        display_obj: DisplayClient | None = None
        try:
            res_pair = (
                [int(resolution[0]), int(resolution[1])]
                if isinstance(resolution, (list, tuple)) and len(resolution) >= 2
                else None
            )
            supports_animation = (
                bool(capabilities["supports_animation"])
                if "supports_animation" in capabilities else None
            )
            display_obj = db.query(DisplayClient).filter(DisplayClient.hostname == hostname).first()
            if not display_obj:
                display_obj = DisplayClient(
                    id=str(uuid.uuid4()),
                    name=metadata.get("name", hostname),
                    location=metadata.get("location", "Unknown"),
                    hostname=hostname,
                    display_type="registered",
                    discovery_method="mqtt_registration",
                    is_online=True,
                    last_seen=datetime.now(timezone.utc),
                    client_version=client_version,
                    orientation=orientation,
                    redis_distribution=bool(capabilities.get("redis_distribution", False)),
                    content_claiming=bool(capabilities.get("content_claiming", False)),
                    supports_animation=supports_animation,
                )
                if res_pair:
                    display_obj.width, display_obj.height = res_pair
                db.add(display_obj)
                db.commit()
                db.refresh(display_obj)
                created = True
            else:
                # Update key fields if changed
                changed = False
                if display_obj.client_version != client_version:
                    display_obj.client_version = client_version
                    changed = True
                if res_pair and [display_obj.width, display_obj.height] != res_pair:
                    display_obj.width, display_obj.height = res_pair
                    changed = True
                if display_obj.orientation != orientation:
                    display_obj.orientation = orientation
                    changed = True
                if supports_animation is not None and display_obj.supports_animation != supports_animation:
                    display_obj.supports_animation = supports_animation
                    changed = True
                if changed:
                    display_obj.last_seen = datetime.now(timezone.utc)
                    db.commit()
            logger.info("%s proactive registration for device_id=%s display_id=%s created=%s", "Accepted", device_id, display_obj.id, created)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.error("DB error handling registration for %s: %s", device_id, e)
            await self._publish_registration_reply(reply_to, assigned_id=device_id, status="error", error=str(e))
            db.close()
            return
        finally:
            db.close()

        # Publish reply (assigned_id echoes device_id for now)
        await self._publish_registration_reply(
            reply_to,
            assigned_id=device_id,
            status="accepted",
            display_id=str(display_obj.id),
            created=created,
            capabilities=capabilities,
        )

        # Immediately send finalize command with registration key (random secret)
        reg_key = secrets.token_hex(16)
        await self._send_finalize_command(device_id=device_id, display_id=str(display_obj.id), registration_key=reg_key)

    async def _publish_registration_reply(
        self,
        reply_to: str,
        *,
        assigned_id: str,
        status: str,
        display_id: str | None = None,
        created: bool | None = None,
        capabilities: dict[str, object] | None = None,
        error: str | None = None,
    ):
        if not self.mqtt_client:
            return
        payload = {
            "assigned_id": assigned_id,
            "status": status,
            "display_id": display_id,
            "created": created,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "capabilities_echo": capabilities,
        }
        if error:
            payload["error"] = error
        try:
            await self.mqtt_client.publish(reply_to, json.dumps(payload), qos=1)
            logger.info("Published registration reply to %s for %s status=%s", reply_to, assigned_id, status)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed publishing registration reply to %s: %s", reply_to, e)

    async def _send_finalize_command(
        self,
        *,
        device_id: str,
        display_id: str,
        registration_key: str,
        client_config: dict | None = None,
    ):
        """Send finalize_registration command to device's /cmd topic.

        client_config is an optional dict that the display client persists to
        device_config.json so it survives reboots without manual .env editing.
        Recognised keys: platform_url, display_name, display_location,
        mqtt_host, mqtt_port, mqtt_username, mqtt_password.
        """
        if not self.mqtt_client:
            return
        cmd_topic = f"mimir/{device_id}/cmd"
        payload: dict = {
            "type": "finalize_registration",
            "display_id": display_id,
            "registration_key": registration_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": 1,
            "source": "pairing_code",
        }
        if client_config:
            payload["config"] = client_config
        try:
            await self.mqtt_client.publish(cmd_topic, json.dumps(payload), qos=1)
            logger.info("Sent finalize_registration to %s display_id=%s", device_id, display_id)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to send finalize command to %s: %s", device_id, e)

    async def _process_registration_reply(self, hostname: str, registration_data: dict[str, object]):
        """Process registration details from a display and create database entry"""
        try:
            capabilities = registration_data.get("capabilities", {})
            metadata = registration_data.get("metadata", {})

            # Create new display in database
            db = SessionLocal()
            try:
                new_display = DisplayClient(
                    id=str(uuid.uuid4()),
                    name=metadata.get("name", f"Display {hostname}"),
                    location=metadata.get("location", "Unknown"),
                    hostname=hostname,
                    display_type="registered",
                    discovery_method="mqtt_registration",
                    is_online=True,
                    last_seen=datetime.now(timezone.utc),
                    client_version=metadata.get("client_version", "unknown"),
                    orientation=capabilities.get("orientation", "landscape"),
                    redis_distribution=bool(capabilities.get("redis_distribution", False)),
                    content_claiming=bool(capabilities.get("content_claiming", False)),
                    supports_animation=(
                        bool(capabilities["supports_animation"])
                        if "supports_animation" in capabilities else None
                    ),
                )
                res = (capabilities.get("resolution")
                       or capabilities.get("native_resolution") or [800, 480])
                if isinstance(res, (list, tuple)) and len(res) >= 2:
                    new_display.width, new_display.height = int(res[0]), int(res[1])

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
