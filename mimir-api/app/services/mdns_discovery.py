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

"""mDNS Discovery Service

Continuously monitors the network for Mimir displays using mDNS/Zeroconf.
"""
from __future__ import annotations

import asyncio
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

from app.config import settings
from app.core.logging import get_logger

try:
    from app.db.database import SessionLocal
    from app.db.models import DisplayClient
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

# Import metrics for instrumentation
try:
    from app.core.metrics import metrics
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class DiscoveredDisplay:
    """Represents a discovered display"""
    service_name: str
    display_id: str
    display_name: str
    hostname: str
    location: str
    addresses: list[str]
    webhook_port: int | None
    resolution: str | None
    client_version: str | None
    properties: dict[str, str]
    discovered_at: datetime
    last_seen: datetime
    is_online: bool = True
    assigned_scene_id: str | None = None
    assigned_subchannel_id: str | None = None


class DisplayDiscoveryListener(ServiceListener):
    """Service listener for mDNS display discovery"""

    def __init__(self, discovery_service: MdnsDiscoveryService):
        self.discovery_service = discovery_service
        self.logger = get_logger(f"{__name__}.DisplayDiscoveryListener")

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        """Called when a new mDNS service is discovered"""
        try:
            if '_mimir-display._tcp.local.' in name:
                self.logger.debug(f"Discovered mDNS service: {name}")
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    display = self._parse_service_info(name, info)
                    if display:
                        self.discovery_service._on_display_discovered(display)
        except Exception as e:
            self.logger.error(f"Error processing discovered service {name}: {e}")

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        """Called when an mDNS service is removed"""
        try:
            if '_mimir-display._tcp.local.' in name:
                self.logger.debug(f"Lost mDNS service: {name}")
                self.discovery_service._on_display_lost(name)
        except Exception as e:
            self.logger.error(f"Error processing removed service {name}: {e}")

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        """Called when an mDNS service is updated"""
        try:
            if '_mimir-display._tcp.local.' in name:
                self.logger.debug(f"Updated mDNS service: {name}")
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    display = self._parse_service_info(name, info)
                    if display:
                        self.discovery_service._on_display_updated(display)
        except Exception as e:
            self.logger.error(f"Error processing updated service {name}: {e}")

    def _parse_service_info(self, service_name: str, info) -> DiscoveredDisplay | None:
        """Parse Zeroconf service info into DiscoveredDisplay"""
        try:
            # Extract properties
            properties = {}
            if info.properties:
                for key, value in info.properties.items():
                    try:
                        properties[key.decode('utf-8')] = value.decode('utf-8')
                    except (UnicodeDecodeError, AttributeError):
                        properties[key.decode('utf-8', errors='ignore')] = str(value)

            # Convert IP addresses to readable format
            addresses = []
            for addr in info.addresses:
                try:
                    if len(addr) == 4:  # IPv4
                        addresses.append(socket.inet_ntoa(addr))
                    elif len(addr) == 16:  # IPv6
                        import ipaddress
                        addresses.append(str(ipaddress.ip_address(addr)))
                except Exception:
                    pass

            # Extract display information
            display_id = properties.get("display_id", f"unknown-{info.server}")
            display_name = properties.get("display_name", f"Display ({properties.get('hostname', 'unknown')})")
            hostname = properties.get("hostname", "unknown")
            location = properties.get("location", "Auto-discovered")
            webhook_port = None

            if properties.get("webhook_port"):
                try:
                    webhook_port = int(properties["webhook_port"])
                except (ValueError, TypeError):
                    pass

            now = datetime.now(timezone.utc)

            return DiscoveredDisplay(
                service_name=service_name,
                display_id=display_id,
                display_name=display_name,
                hostname=hostname,
                location=location,
                addresses=addresses,
                webhook_port=webhook_port,
                resolution=properties.get("resolution"),
                client_version=properties.get("client_version"),
                properties=properties,
                discovered_at=now,
                last_seen=now
            )

        except Exception as e:
            self.logger.error(f"Failed to parse service info for {service_name}: {e}")
            return None


class MdnsDiscoveryService:
    """Service for continuous mDNS discovery of Mimir displays"""

    def __init__(self):
        self.is_running = False
        self.zeroconf: Zeroconf | None = None
        self.browser: ServiceBrowser | None = None
        self.listener: DisplayDiscoveryListener | None = None
        self.discovered_displays: dict[str, DiscoveredDisplay] = {}
        self.discovery_callbacks: list[Callable[[DiscoveredDisplay, str], None]] = []
        self._lock = threading.Lock()
        self._monitoring_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Settings
        self.update_interval = settings.mdns_update_interval  # seconds
        self.offline_timeout = settings.mdns_offline_timeout  # seconds

        # Mapping from display_id to service_name for quick lookup
        self.display_id_to_service_name: dict[str, str] = {}
        # Last MQTT heartbeat timestamps
        self.mqtt_last_heartbeat: dict[str, datetime] = {}

    @property
    def is_available(self) -> bool:
        """Check if discovery is available.

        Availability can come from either:
        - native Zeroconf browsing (requires `zeroconf`), or
        - external feed mode (events ingested via API from a host-network sidecar).
        """
        return bool(getattr(settings, "mdns_external_feed_enabled", False)) or ZEROCONF_AVAILABLE

    def add_discovery_callback(self, callback: Callable[[DiscoveredDisplay, str], None]):
        """Add callback for discovery events (discovered, updated, lost)"""
        with self._lock:
            self.discovery_callbacks.append(callback)

    def remove_discovery_callback(self, callback: Callable[[DiscoveredDisplay, str], None]):
        """Remove discovery callback"""
        with self._lock:
            if callback in self.discovery_callbacks:
                self.discovery_callbacks.remove(callback)

    async def start_discovery(self) -> bool:
        """Start continuous mDNS discovery"""
        if not self.is_available:
            logger.warning("mDNS discovery not available - zeroconf library not installed")
            return False

        if self.is_running:
            logger.warning("mDNS discovery already running")
            return True

        try:
            logger.info("Starting mDNS discovery service for Mimir displays")

            # Capture the running event loop so callbacks fired from Zeroconf's
            # native worker thread can schedule coroutines safely.
            self._loop = asyncio.get_running_loop()

            # Initialize Zeroconf
            self.zeroconf = Zeroconf()
            self.listener = DisplayDiscoveryListener(self)

            # Start service browser
            self.browser = ServiceBrowser(
                self.zeroconf,
                "_mimir-display._tcp.local.",
                self.listener
            )

            self.is_running = True

            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

            logger.info("mDNS discovery service started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start mDNS discovery: {e}")
            await self.stop_discovery()
            return False

    async def start_external_feed(self) -> bool:
        """Start discovery bookkeeping without binding to multicast.

        This mode is intended for accepting discovery events from a separate
        host-network "edge" service (Linux) that can reliably do mDNS browsing.
        """
        if self.is_running:
            logger.warning("mDNS discovery already running")
            return True

        logger.info("Starting external mDNS discovery feed mode")
        self._loop = asyncio.get_running_loop()
        self.is_running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        return True

    def ingest_external_event(
        self,
        *,
        event: str,
        service_name: str,
        properties: dict[str, str] | None = None,
        addresses: list[str] | None = None,
        webhook_port: int | None = None,
        seen_at: datetime | None = None,
    ) -> None:
        """Ingest a discovery event from an external service.

        Supported events: discovered, updated, lost.
        """
        evt = (event or "").strip().lower()
        if evt == "lost":
            self._on_display_lost(service_name)
            return
        if evt not in ("discovered", "updated"):
            raise ValueError(f"Unsupported event: {event}")

        props = properties or {}
        now = seen_at or datetime.now(timezone.utc)

        display_id = props.get("display_id") or props.get("device_id") or service_name
        display_name = props.get("display_name") or f"Display ({props.get('hostname', display_id)})"
        hostname = props.get("hostname") or display_id
        location = props.get("location") or "Auto-discovered"
        resolution = props.get("resolution")
        client_version = props.get("client_version")

        display = DiscoveredDisplay(
            service_name=service_name,
            display_id=display_id,
            display_name=display_name,
            hostname=hostname,
            location=location,
            addresses=list(addresses or []),
            webhook_port=webhook_port,
            resolution=resolution,
            client_version=client_version,
            properties=props,
            discovered_at=now,
            last_seen=now,
        )
        self._on_display_updated(display) if evt == "updated" else self._on_display_discovered(display)

    async def stop_discovery(self):
        """Stop mDNS discovery"""
        if not self.is_running:
            return

        logger.info("Stopping mDNS discovery service")

        self.is_running = False

        # Cancel monitoring task
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        # Cleanup Zeroconf
        try:
            if self.browser:
                self.browser.cancel()
            if self.zeroconf:
                self.zeroconf.close()
        except Exception as e:
            logger.error(f"Error during mDNS cleanup: {e}")
        finally:
            self.browser = None
            self.zeroconf = None
            self.listener = None

        # Clear discovered displays
        with self._lock:
            self.discovered_displays.clear()

        logger.info("mDNS discovery service stopped")

    def get_discovered_displays(self) -> list[DiscoveredDisplay]:
        """Get list of currently discovered displays"""
        with self._lock:
            return list(self.discovered_displays.values())

    def get_display_by_id(self, display_id: str) -> DiscoveredDisplay | None:
        """Get discovered display by ID"""
        with self._lock:
            for display in self.discovered_displays.values():
                if display.display_id == display_id:
                    return display
            return None

    def get_display_by_hostname(self, hostname: str) -> DiscoveredDisplay | None:
        """Get discovered display by hostname"""
        with self._lock:
            for display in self.discovered_displays.values():
                if display.hostname == hostname:
                    return display
            return None

    def _on_display_discovered(self, display: DiscoveredDisplay):
        """Handle newly discovered display"""
        with self._lock:
            existing = self.discovered_displays.get(display.service_name)

            # Map display_id to service_name for quick lookup
            self.display_id_to_service_name[display.display_id] = display.service_name

            if existing:
                # Update existing display
                existing.last_seen = display.last_seen
                existing.is_online = True
                existing.addresses = display.addresses
                existing.properties = display.properties
                if display.webhook_port is not None:
                    existing.webhook_port = display.webhook_port
                logger.debug(f"Updated discovered display: {display.display_name} ({display.hostname})")

                # Record metrics for display update
                if METRICS_AVAILABLE:
                    metrics.discovery_display_updated(display.display_id)

                self._notify_callbacks(existing, "updated")
            else:
                # New display
                self.discovered_displays[display.service_name] = display
                logger.info(f"Discovered new display: {display.display_name} ({display.hostname}) at {display.addresses}")

                # Record metrics for new display discovery
                if METRICS_AVAILABLE:
                    metrics.discovery_display_found(display.display_id)

                self._notify_callbacks(display, "discovered")

    def _on_display_updated(self, display: DiscoveredDisplay):
        """Handle updated display"""
        self._on_display_discovered(display)  # Same logic as discovery

    def forget_display(self, display_id: str) -> bool:
        """Remove a display from the in-memory discovery cache by display_id.

        Called when a display is deleted/unpaired so it stops appearing in the
        Screens UI. Returns True if an entry was removed, False if not found.
        """
        with self._lock:
            service_name = self.display_id_to_service_name.get(display_id)
            if not service_name:
                # Fallback: scan by display_id in case the id map is stale
                for sn, d in list(self.discovered_displays.items()):
                    if d.display_id == display_id:
                        service_name = sn
                        break
            if service_name:
                self.discovered_displays.pop(service_name, None)
                self.display_id_to_service_name.pop(display_id, None)
                logger.info("Evicted display %s (%s) from discovery cache", display_id, service_name)
                return True
            return False

    def _on_display_lost(self, service_name: str):
        """Handle lost display"""
        with self._lock:
            display = self.discovered_displays.get(service_name)
            if display:
                display.is_online = False
                logger.info(f"Display went offline: {display.display_name} ({display.hostname})")

                # Record metrics for display going offline
                if METRICS_AVAILABLE:
                    metrics.discovery_display_lost(display.display_id)

                self._notify_callbacks(display, "lost")

    def _notify_callbacks(self, display: DiscoveredDisplay, event: str):
        """Notify registered callbacks.

        This may be invoked from Zeroconf's native callback thread (via
        add_service/remove_service/update_service), not the asyncio event-loop
        thread, so coroutine callbacks must be scheduled thread-safely.
        """
        for callback in self.discovery_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Schedule the coroutine on the event loop from whichever
                    # thread we're called on.
                    if self._loop is not None:
                        asyncio.run_coroutine_threadsafe(callback(display, event), self._loop)
                    else:
                        logger.error("Cannot schedule discovery callback: no event loop captured")
                else:
                    callback(display, event)
            except Exception as e:
                logger.error(f"Error in discovery callback: {e}")

    def update_display_heartbeat(self, display_id: str, heartbeat_timestamp: datetime, heartbeat_data: dict | None = None):
        """
        Update display's last_seen and online status from MQTT heartbeat.

        Args:
            display_id: The device_id from MQTT heartbeat.
            heartbeat_timestamp: The timestamp from the heartbeat payload.
            heartbeat_data: Optional heartbeat payload data containing scene assignments.
        """
        logger.info("Processing heartbeat for device_id=%s timestamp=%s", display_id, heartbeat_timestamp)

        with self._lock:
            # Resolve service name if we have seen this display before
            service_name = self.display_id_to_service_name.get(display_id)

            # Fallback: search by display_id across discovered objects
            if not service_name:
                for sn, disp in self.discovered_displays.items():
                    if disp.display_id == display_id or disp.hostname == display_id:
                        service_name = sn
                        self.display_id_to_service_name[display_id] = sn
                        break

            # New display via heartbeat
            if not service_name:
                service_name = f"mqtt-{display_id}"
                # Load the authoritative assignment from the DB rather than trusting
                # what the display reports it's currently showing.
                db_scene_id: str | None = None
                db_subchannel_id: str | None = None
                if _DB_AVAILABLE:
                    try:
                        with SessionLocal() as _db:
                            _rec = _db.query(DisplayClient).filter(
                                (DisplayClient.id == display_id) | (DisplayClient.hostname == display_id)
                            ).first()
                            if _rec:
                                db_scene_id = _rec.assigned_scene_id
                    except Exception as _db_err:
                        logger.debug("heartbeat.db_lookup_failed display=%s err=%s", display_id, _db_err)
                placeholder = DiscoveredDisplay(
                    service_name=service_name,
                    display_id=display_id,
                    display_name=f"Display ({display_id})",
                    hostname=display_id,
                    location="MQTT heartbeat",
                    addresses=[],
                    webhook_port=None,
                    resolution=None,
                    client_version=None,
                    properties={},
                    discovered_at=heartbeat_timestamp,
                    last_seen=heartbeat_timestamp,
                    is_online=True,
                    assigned_scene_id=db_scene_id,
                    assigned_subchannel_id=db_subchannel_id,
                )
                self._enrich_from_heartbeat(placeholder, heartbeat_data)
                self.discovered_displays[service_name] = placeholder
                self.display_id_to_service_name[display_id] = service_name
                logger.info("Discovered new display via heartbeat: %s (%s)", placeholder.display_name, placeholder.hostname)
                if METRICS_AVAILABLE:
                    metrics.discovery_display_found(placeholder.display_id)
                self._notify_callbacks(placeholder, "discovered")
                display = placeholder
            else:
                display = self.discovered_displays.get(service_name)
                if not display:
                    logger.error("Resolved service_name %s for %s but no display object present", service_name, display_id)
                    return
                prev_online = display.is_online
                logger.debug(
                    "Heartbeat update for %s last_seen %s -> %s online=%s",
                    display.display_name,
                    display.last_seen,
                    heartbeat_timestamp,
                    display.is_online,
                )
                display.last_seen = heartbeat_timestamp
                # Do not overwrite assigned_scene_id/subchannel_id from the heartbeat.
                # The heartbeat reports what the display is *currently showing*, which
                # lags behind the server's assignment during transitions. The platform
                # is authoritative; assignments are set only via the explicit assign route.
                self._enrich_from_heartbeat(display, heartbeat_data)
                if not prev_online:
                    display.is_online = True
                    logger.info("Display back online via heartbeat: %s", display.display_name)
                    self._notify_callbacks(display, "discovered")  # treat as rediscovery
                else:
                    self._notify_callbacks(display, "updated")

            # Track heartbeat time (also map via hostname for convenience)
            self.mqtt_last_heartbeat[display_id] = heartbeat_timestamp
            if display.hostname and display.hostname != display_id:
                self.mqtt_last_heartbeat[display.hostname] = heartbeat_timestamp
            logger.debug("Recorded heartbeat timestamp for %s", display_id)

    def _enrich_from_heartbeat(self, display_obj: DiscoveredDisplay, hb: dict | None):
        """Merge capability-style heartbeat data into a discovered display.

        Normalizes keys so the HTTP layer can rely on unified property names.
        Populates:
          properties['resolution'] -> 'WIDTHxHEIGHT'
          properties['orientation']
          properties['formats'] (list[str])
          properties['redis_distribution'] / 'content_claiming' as 'true'/'false'
        Also updates display_obj.resolution shortcut if derived.
        """
        if not hb:
            return
        props = display_obj.properties
        if props is None:  # defensive – should always be dict
            props = {}
            display_obj.properties = props

        cap = hb.get("cap") or {}

        # Resolution candidates
        res = hb.get("res") or cap.get("res") or cap.get("resolution") or cap.get("native_resolution")
        if isinstance(res, (list, tuple)) and len(res) == 2 and all(isinstance(v, (int, float)) for v in res):
            try:
                w, h = int(res[0]), int(res[1])
                if w > 0 and h > 0:
                    props["resolution"] = f"{w}x{h}"
                    display_obj.resolution = props["resolution"]
            except (ValueError, TypeError):  # pragma: no cover - defensive
                pass

        # Orientation
        orientation = cap.get("ori") or cap.get("orientation") or hb.get("orientation")
        if orientation:
            props["orientation"] = str(orientation)

        # Formats
        formats = cap.get("formats") or cap.get("supported_formats") or cap.get("supportedFormats")
        if isinstance(formats, (list, tuple)) and formats:
            # dedupe preserving order
            props["formats"] = list(dict.fromkeys(str(f) for f in formats))

        # Boolean capabilities -> string flags
        for key in ("redis_distribution", "content_claiming"):
            val = cap.get(key)
            if isinstance(val, bool):
                props[key] = "true" if val else "false"

        # Webhook port — allows pairing to work even when the display was
        # discovered via heartbeat before mDNS fired. Clients >= current emit
        # this so the server never gets stuck with webhook_port=None.
        webhook_port = hb.get("webhook_port")
        if webhook_port is not None:
            try:
                display_obj.webhook_port = int(webhook_port)
            except (ValueError, TypeError):
                pass

        # Version reporting (Phase 2): clients >= 1.0.4 include these in
        # heartbeat/status payloads. Drives the fleet panel and OTA rollouts.
        client_version = hb.get("client_version")
        if client_version:
            display_obj.client_version = str(client_version)
            props["client_version"] = str(client_version)
        protocol_version = hb.get("protocol_version")
        if protocol_version is not None:
            props["protocol_version"] = str(protocol_version)

        # OTA state (Phase 3): canary marker + last update outcome.
        if isinstance(hb.get("canary"), bool):
            props["canary"] = "true" if hb["canary"] else "false"
        update_status = hb.get("update_status")
        if update_status:
            props["update_status"] = str(update_status)
            for key in ("update_target", "update_error"):
                if hb.get(key) is not None:
                    props[key] = str(hb[key])
                else:
                    props.pop(key, None)  # clear stale detail from a previous attempt

    async def _monitoring_loop(self):
        """Background monitoring loop for display health"""
        while self.is_running:
            try:
                await asyncio.sleep(self.update_interval)
                if not self.is_running:
                    break
                now = datetime.now(timezone.utc)
                with self._lock:
                    for display in list(self.discovered_displays.values()):
                        last_seen = display.last_seen
                        heartbeat_seen = self.mqtt_last_heartbeat.get(display.display_id)
                        if not heartbeat_seen and display.hostname:
                            heartbeat_seen = self.mqtt_last_heartbeat.get(display.hostname)
                        if heartbeat_seen and heartbeat_seen > last_seen:
                            last_seen = heartbeat_seen
                        time_since_seen = (now - last_seen).total_seconds()
                        logger.debug(
                            "Display %s: last_seen=%s, time_since_seen=%.1fs, offline_timeout=%ss",
                            display.display_name,
                            last_seen,
                            time_since_seen,
                            self.offline_timeout,
                        )
                        if display.is_online and time_since_seen > self.offline_timeout:
                            display.is_online = False
                            logger.info(
                                "Display marked offline due to timeout: %s (last seen %.1fs ago)",
                                display.display_name,
                                time_since_seen,
                            )
                            if METRICS_AVAILABLE:
                                metrics.discovery_display_lost(display.display_id)
                            self._notify_callbacks(display, "lost")
                if METRICS_AVAILABLE:
                    total_displays = len(self.discovered_displays)
                    online_displays = sum(1 for d in self.discovered_displays.values() if d.is_online)
                    metrics.discovery_displays_total(total_displays)
                    metrics.discovery_displays_online(online_displays)
            except asyncio.CancelledError:
                break
            except Exception as e:  # pragma: no cover - defensive
                logger.error("Error in discovery monitoring loop: %s", e)
                if METRICS_AVAILABLE:
                    metrics.discovery_error(str(e))
                await asyncio.sleep(10)

    def get_discovery_stats(self) -> dict[str, Any]:
        """Get discovery statistics"""
        with self._lock:
            total_displays = len(self.discovered_displays)
            online_displays = sum(1 for d in self.discovered_displays.values() if d.is_online)

            mode = "stopped"
            if self.is_running:
                mode = "native" if self.zeroconf is not None else "external_feed"

            return {
                "is_running": self.is_running,
                "is_available": self.is_available,
                "mode": mode,
                "external_feed_enabled": bool(getattr(settings, "mdns_external_feed_enabled", False)),
                "total_discovered": total_displays,
                "online_displays": online_displays,
                "offline_displays": total_displays - online_displays,
                "update_interval": self.update_interval,
                "offline_timeout": self.offline_timeout
            }


# Global service instance
mdns_discovery_service = MdnsDiscoveryService()
