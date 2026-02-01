#!/usr/bin/env python3

"""
Standalone mDNS discovery test for Mimir displays
Run this on the API server to test if mDNS discovery is working
"""

from zeroconf import Zeroconf, ServiceBrowser
import time
import json

def test_discovery():
    print("🔍 Testing mDNS discovery for Mimir displays...")
    
    discovered_displays = []
    
    class DisplayServiceListener:
        def add_service(self, zeroconf, service_type, name):
            print(f"🔎 Found service: {name}")
            if '_mimir-display._tcp.local.' in name:
                print(f"✅ Processing mimir display service: {name}")
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    # Extract service properties
                    properties = {}
                    if info.properties:
                        for key, value in info.properties.items():
                            try:
                                properties[key.decode('utf-8')] = value.decode('utf-8')
                            except:
                                pass
                    
                    # Get IP addresses
                    addresses = [addr for addr in info.addresses if addr]
                    
                    hostname = properties.get("hostname", "unknown")
                    display_name = properties.get("display_name", f"Display ({hostname})")
                    
                    display_info = {
                        "service_name": name,
                        "hostname": hostname,
                        "display_name": display_name,
                        "display_id": properties.get("display_id"),
                        "location": properties.get("location", "Auto-discovered"),
                        "resolution": properties.get("resolution"),
                        "client_version": properties.get("client_version"),
                        "webhook_port": properties.get("webhook_port"),
                        "addresses": [str(addr) for addr in addresses],
                        "port": info.port,
                        "properties": properties
                    }
                    
                    discovered_displays.append(display_info)
                    print(f"✅ Added display: {display_name} ({hostname})")
                    print(f"   Address: {addresses}")
                    print(f"   Properties: {properties}")
        
        def remove_service(self, zeroconf, service_type, name):
            if '_mimir-display._tcp.local.' in name:
                print(f"🔄 Removed service: {name}")
        
        def update_service(self, zeroconf, service_type, name):
            if '_mimir-display._tcp.local.' in name:
                print(f"🔄 Updated service: {name}")
    
    # Start discovery
    zeroconf = Zeroconf()
    listener = DisplayServiceListener()
    browser = ServiceBrowser(zeroconf, "_mimir-display._tcp.local.", listener)
    
    print("⏳ Waiting 15 seconds for services...")
    time.sleep(15)
    
    # Cleanup
    browser.cancel()
    zeroconf.close()
    
    print(f"\n✅ Discovery complete!")
    print(f"Found {len(discovered_displays)} displays:")
    
    for display in discovered_displays:
        print(f"\n📱 {display['display_name']}")
        print(f"   Hostname: {display['hostname']}")
        print(f"   Service: {display['service_name']}")
        print(f"   Address: {display['addresses']}")
        print(f"   Webhook Port: {display['webhook_port']}")
    
    return discovered_displays

if __name__ == "__main__":
    displays = test_discovery()
    print(f"\n📊 Final result: {len(displays)} displays discovered")
    if displays:
        print(json.dumps(displays, indent=2))
