"""
mDNS Discovery Service
Continuously monitors the network for Mimir displays using mDNS/Zeroconf
"""
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
import socket
import threading
from dataclasses import dataclass

try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import DisplayClient

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
    addresses: List[str]
    webhook_port: Optional[int]
    resolution: Optional[str]
    client_version: Optional[str]
    properties: Dict[str, str]
    discovered_at: datetime
    last_seen: datetime
    is_online: bool = True


class DisplayDiscoveryListener(ServiceListener):
    """Service listener for mDNS display discovery"""
    
    def __init__(self, discovery_service: 'MdnsDiscoveryService'):
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
    
    def _parse_service_info(self, service_name: str, info) -> Optional[DiscoveredDisplay]:
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
        self.zeroconf: Optional[Zeroconf] = None
        self.browser: Optional[ServiceBrowser] = None
        self.listener: Optional[DisplayDiscoveryListener] = None
        self.discovered_displays: Dict[str, DiscoveredDisplay] = {}
        self.discovery_callbacks: List[Callable[[DiscoveredDisplay, str], None]] = []
        self._lock = threading.Lock()
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Settings  
        self.update_interval = settings.mdns_update_interval  # seconds
        self.offline_timeout = settings.mdns_offline_timeout  # seconds

        # Mapping from display_id to service_name for quick lookup
        self.display_id_to_service_name: Dict[str, str] = {}
        # Last MQTT heartbeat timestamps
        self.mqtt_last_heartbeat: Dict[str, datetime] = {}
    
    @property
    def is_available(self) -> bool:
        """Check if mDNS discovery is available"""
        return ZEROCONF_AVAILABLE
    
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
    
    def get_discovered_displays(self) -> List[DiscoveredDisplay]:
        """Get list of currently discovered displays"""
        with self._lock:
            return list(self.discovered_displays.values())
    
    def get_display_by_id(self, display_id: str) -> Optional[DiscoveredDisplay]:
        """Get discovered display by ID"""
        with self._lock:
            for display in self.discovered_displays.values():
                if display.display_id == display_id:
                    return display
            return None
    
    def get_display_by_hostname(self, hostname: str) -> Optional[DiscoveredDisplay]:
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
        """Notify registered callbacks"""
        import asyncio
        for callback in self.discovery_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Schedule the coroutine in the event loop
                    asyncio.create_task(callback(display, event))
                else:
                    callback(display, event)
            except Exception as e:
                logger.error(f"Error in discovery callback: {e}")
    
    def update_display_heartbeat(self, display_id: str, heartbeat_timestamp: datetime):
        """
        Update display's last_seen and online status from MQTT heartbeat.

        Args:
            display_id: The device_id from MQTT heartbeat.
            heartbeat_timestamp: The timestamp from the heartbeat payload.
        """
        with self._lock:
            service_name = self.display_id_to_service_name.get(display_id)
            if not service_name:
                # Display not discovered via mDNS yet, create a placeholder
                service_name = f"mqtt-{display_id}"
                self.display_id_to_service_name[display_id] = service_name
                display = DiscoveredDisplay(
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
                )
                self.discovered_displays[service_name] = display
                logger.info(f"Discovered new display via MQTT heartbeat: {display.display_name} ({display.hostname})")
                if METRICS_AVAILABLE:
                    metrics.discovery_display_found(display.display_id)
                self._notify_callbacks(display, "discovered")
            else:
                display = self.discovered_displays.get(service_name)
                if display:
                    display.last_seen = heartbeat_timestamp
                    if not display.is_online:
                        display.is_online = True
                        logger.info(f"Display back online via MQTT heartbeat: {display.display_name} ({display.hostname})")
                        if METRICS_AVAILABLE:
                            metrics.discovery_display_found(display.display_id)
                        self._notify_callbacks(display, "discovered")
            self.mqtt_last_heartbeat[display_id] = heartbeat_timestamp

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
                        # Use the most recent of mDNS or MQTT heartbeat
                        last_seen = display.last_seen
                        heartbeat_seen = self.mqtt_last_heartbeat.get(display.display_id)
                        if heartbeat_seen and heartbeat_seen > last_seen:
                            last_seen = heartbeat_seen

                        time_since_seen = (now - last_seen).total_seconds()
                        if display.is_online and time_since_seen > self.offline_timeout:
                            display.is_online = False
                            logger.info(f"Display marked offline due to timeout: {display.display_name}")
                            if METRICS_AVAILABLE:
                                metrics.discovery_display_lost(display.display_id)
                            self._notify_callbacks(display, "lost")

                # Record general discovery metrics
                if METRICS_AVAILABLE:
                    total_displays = len(self.discovered_displays)
                    online_displays = sum(1 for d in self.discovered_displays.values() if d.is_online)
                    metrics.discovery_displays_total(total_displays)
                    metrics.discovery_displays_online(online_displays)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in discovery monitoring loop: {e}")
                
                # Record metrics for monitoring errors
                if METRICS_AVAILABLE:
                    metrics.discovery_error(str(e))
            except Exception as e:
                logger.error(f"Error in mDNS monitoring loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """Get discovery statistics"""
        with self._lock:
            total_displays = len(self.discovered_displays)
            online_displays = sum(1 for d in self.discovered_displays.values() if d.is_online)
            
            return {
                "is_running": self.is_running,
                "is_available": self.is_available,
                "total_discovered": total_displays,
                "online_displays": online_displays,
                "offline_displays": total_displays - online_displays,
                "update_interval": self.update_interval,
                "offline_timeout": self.offline_timeout
            }


# Global service instance
mdns_discovery_service = MdnsDiscoveryService()
