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
        self.auto_register = settings.mdns_auto_register
        self.update_interval = settings.mdns_update_interval  # seconds
        self.offline_timeout = settings.mdns_offline_timeout  # seconds
    
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
            
            if existing:
                # Update existing display
                existing.last_seen = display.last_seen
                existing.is_online = True
                existing.addresses = display.addresses
                existing.properties = display.properties
                logger.debug(f"Updated discovered display: {display.display_name} ({display.hostname})")
                self._notify_callbacks(existing, "updated")
            else:
                # New display
                self.discovered_displays[display.service_name] = display
                logger.info(f"Discovered new display: {display.display_name} ({display.hostname}) at {display.addresses}")
                self._notify_callbacks(display, "discovered")
                
                # Auto-register if enabled
                if self.auto_register:
                    asyncio.create_task(self._auto_register_display(display))
    
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
                self._notify_callbacks(display, "lost")
    
    def _notify_callbacks(self, display: DiscoveredDisplay, event: str):
        """Notify registered callbacks"""
        for callback in self.discovery_callbacks:
            try:
                callback(display, event)
            except Exception as e:
                logger.error(f"Error in discovery callback: {e}")
    
    async def _auto_register_display(self, display: DiscoveredDisplay):
        """Automatically register discovered display in database"""
        try:
            db = SessionLocal()
            try:
                # Check if display already exists
                existing = db.query(DisplayClient).filter(
                    DisplayClient.hostname == display.hostname
                ).first()
                
                if existing:
                    # Update existing display
                    existing.is_online = True
                    existing.last_seen = datetime.now()
                    existing.display_type = "discovered"
                    existing.discovery_method = "mdns"
                    db.commit()
                    logger.debug(f"Updated existing display registration: {display.display_name}")
                else:
                    # Create new display record
                    resolution = display.resolution or "800x480"
                    try:
                        width, height = map(int, resolution.split("x"))
                    except (ValueError, AttributeError):
                        width, height = 800, 480
                    
                    new_client = DisplayClient(
                        id=display.display_id,
                        name=display.display_name,
                        location=display.location,
                        hostname=display.hostname,
                        webhook_port=display.webhook_port,
                        width=width,
                        height=height,
                        orientation=display.properties.get("orientation", "landscape"),
                        client_version=display.client_version or "unknown",
                        redis_distribution=display.properties.get("redis_distribution") == "true",
                        content_claiming=display.properties.get("content_claiming") == "true",
                        display_type="discovered",
                        discovery_method="mdns",
                        auto_discovered=True,
                        is_online=True,
                        last_seen=datetime.now()
                    )
                    
                    db.add(new_client)
                    db.commit()
                    logger.info(f"Auto-registered new display: {display.display_name} ({display.hostname})")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to auto-register display {display.display_name}: {e}")
    
    async def _monitoring_loop(self):
        """Background monitoring loop for display health"""
        while self.is_running:
            try:
                await asyncio.sleep(self.update_interval)
                
                if not self.is_running:
                    break
                
                # Check for displays that haven't been seen recently
                now = datetime.now(timezone.utc)
                with self._lock:
                    for display in list(self.discovered_displays.values()):
                        if display.is_online:
                            time_since_seen = (now - display.last_seen).total_seconds()
                            if time_since_seen > self.offline_timeout:
                                display.is_online = False
                                logger.info(f"Display marked offline due to timeout: {display.display_name}")
                                self._notify_callbacks(display, "lost")
                                
                                # Update database
                                if self.auto_register:
                                    asyncio.create_task(self._update_display_offline(display))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in mDNS monitoring loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def _update_display_offline(self, display: DiscoveredDisplay):
        """Update display as offline in database"""
        try:
            db = SessionLocal()
            try:
                existing = db.query(DisplayClient).filter(
                    DisplayClient.hostname == display.hostname
                ).first()
                
                if existing:
                    existing.is_online = False
                    existing.last_seen = datetime.now()
                    db.commit()
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to update display offline status: {e}")
    
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
                "auto_register": self.auto_register,
                "update_interval": self.update_interval,
                "offline_timeout": self.offline_timeout
            }


# Global service instance
mdns_discovery_service = MdnsDiscoveryService()
