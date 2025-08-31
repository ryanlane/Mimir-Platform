#!/usr/bin/env python3

"""
Test zeroconf compatibility and network discovery
"""

import sys
import time

def test_zeroconf_import():
    """Test zeroconf import and version compatibility"""
    try:
        import zeroconf
        print(f"✅ Zeroconf imported successfully")
        print(f"   Version: {zeroconf.__version__}")
        
        # Test basic classes
        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
            print(f"✅ Core classes imported successfully")
            return True
        except ImportError as e:
            print(f"❌ Failed to import core classes: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Zeroconf not available: {e}")
        return False

def test_zeroconf_functionality():
    """Test actual zeroconf functionality"""
    try:
        from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
        import socket
        
        print("🔍 Testing zeroconf functionality...")
        
        discovered_services = []
        
        class TestListener(ServiceListener):
            def add_service(self, zeroconf, service_type, name):
                print(f"  Found service: {name}")
                if '_mimir-display._tcp.local.' in name:
                    info = zeroconf.get_service_info(service_type, name)
                    if info:
                        print(f"  ✅ Got service info for: {name}")
                        
                        # Extract properties
                        properties = {}
                        if info.properties:
                            for key, value in info.properties.items():
                                try:
                                    properties[key.decode('utf-8')] = value.decode('utf-8')
                                except:
                                    pass
                        
                        # Convert addresses
                        addresses = []
                        for addr in info.addresses:
                            try:
                                addresses.append(socket.inet_ntoa(addr))
                            except:
                                addresses.append(str(addr))
                        
                        service_info = {
                            "name": name,
                            "addresses": addresses,
                            "port": info.port,
                            "properties": properties
                        }
                        discovered_services.append(service_info)
                        print(f"     Addresses: {addresses}")
                        print(f"     Properties: {properties}")
            
            def remove_service(self, zeroconf, service_type, name):
                pass
            
            def update_service(self, zeroconf, service_type, name):
                pass
        
        # Start discovery
        print("  Starting discovery...")
        zeroconf = Zeroconf()
        listener = TestListener()
        browser = ServiceBrowser(zeroconf, "_mimir-display._tcp.local.", listener)
        
        # Wait for discovery
        print("  Waiting 10 seconds for services...")
        time.sleep(10)
        
        # Cleanup
        browser.cancel()
        zeroconf.close()
        
        print(f"✅ Discovery completed. Found {len(discovered_services)} mimir displays")
        for service in discovered_services:
            print(f"  📱 {service['name']}")
            print(f"     Addresses: {service['addresses']}")
        
        return len(discovered_services) > 0
        
    except Exception as e:
        print(f"❌ Zeroconf functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Zeroconf Compatibility Test")
    print("=" * 40)
    
    # Test import
    import_ok = test_zeroconf_import()
    if not import_ok:
        print("\n❌ Cannot proceed - zeroconf not available")
        return
    
    print()
    
    # Test functionality  
    discovery_ok = test_zeroconf_functionality()
    
    print()
    print("📊 Summary:")
    print(f"  Import:    {'✅ OK' if import_ok else '❌ Failed'}")
    print(f"  Discovery: {'✅ OK' if discovery_ok else '❌ Failed'}")
    
    if import_ok and discovery_ok:
        print("\n🎉 Zeroconf is working properly!")
    elif import_ok and not discovery_ok:
        print("\n⚠️ Zeroconf imported but discovery failed")
        print("   This could be a network/timing issue")
    else:
        print("\n❌ Zeroconf has compatibility issues")

if __name__ == "__main__":
    main()
