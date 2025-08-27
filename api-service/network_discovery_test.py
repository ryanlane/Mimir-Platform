#!/usr/bin/env python3

"""
Network discovery diagnostics for mDNS
"""

import subprocess
import socket
import time

def test_basic_connectivity():
    """Test basic network connectivity to the display"""
    print("🔍 Testing basic connectivity...")
    
    display_ip = "192.168.1.41"
    display_port = 8081
    
    try:
        # Test ping
        result = subprocess.run(["ping", "-c", "1", display_ip], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ Ping to {display_ip}: OK")
        else:
            print(f"❌ Ping to {display_ip}: Failed")
            
        # Test webhook port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((display_ip, display_port))
        sock.close()
        
        if result == 0:
            print(f"✅ Webhook port {display_port}: Accessible")
        else:
            print(f"❌ Webhook port {display_port}: Not accessible")
            
    except Exception as e:
        print(f"❌ Connectivity test failed: {e}")

def test_mdns_tools():
    """Test mDNS discovery using system tools"""
    print("\n🔍 Testing mDNS discovery tools...")
    
    # Test with avahi-browse
    try:
        print("  Testing with avahi-browse...")
        result = subprocess.run(
            ["avahi-browse", "-r", "_mimir-display._tcp", "-t"],
            capture_output=True, text=True, timeout=15
        )
        
        if "_mimir-display._tcp" in result.stdout:
            print("  ✅ avahi-browse found mimir display services")
            print("  Raw output:")
            for line in result.stdout.split('\n'):
                if 'mimir-display' in line or '_mimir-display' in line:
                    print(f"    {line}")
        else:
            print("  ❌ avahi-browse: No mimir display services found")
            
    except FileNotFoundError:
        print("  ⚠️ avahi-browse not available")
    except subprocess.TimeoutExpired:
        print("  ⏱️ avahi-browse timed out")
    except Exception as e:
        print(f"  ❌ avahi-browse error: {e}")
    
    # Test with dig for mDNS
    try:
        print("  Testing with dig...")
        result = subprocess.run(
            ["dig", "@224.0.0.251", "-p", "5353", "_mimir-display._tcp.local.", "PTR"],
            capture_output=True, text=True, timeout=10
        )
        
        if "_mimir-display._tcp" in result.stdout:
            print("  ✅ dig found mimir display services")
        else:
            print("  ❌ dig: No mimir display services found")
            
    except Exception as e:
        print(f"  ❌ dig error: {e}")

def test_manual_mdns_query():
    """Test manual mDNS query using Python"""
    print("\n🔍 Testing manual mDNS query...")
    
    try:
        import socket
        import struct
        
        # Create UDP socket for mDNS
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        # mDNS query for _mimir-display._tcp.local
        mdns_group = ("224.0.0.251", 5353)
        
        # Simple mDNS query packet (this is a simplified version)
        query = b'\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'  # Header
        query += b'\x0c_mimir-display\x04_tcp\x05local\x00'  # Query name
        query += b'\x00\x0c\x00\x01'  # PTR query, class IN
        
        sock.sendto(query, mdns_group)
        print("  📡 Sent mDNS query for _mimir-display._tcp.local")
        
        # Try to receive responses
        try:
            while True:
                data, addr = sock.recvfrom(1024)
                if addr[0] == "192.168.1.41":  # Response from our display
                    print(f"  ✅ Received mDNS response from display at {addr}")
                    break
        except socket.timeout:
            print("  ❌ No mDNS response received within timeout")
            
        sock.close()
        
    except Exception as e:
        print(f"  ❌ Manual mDNS query failed: {e}")

def main():
    print("🧪 Network Discovery Diagnostics")
    print("=" * 40)
    
    test_basic_connectivity()
    test_mdns_tools()
    test_manual_mdns_query()
    
    print("\n📊 Summary:")
    print("If basic connectivity works but mDNS discovery fails,")
    print("the issue is likely:")
    print("1. Firewall blocking mDNS (UDP port 5353)")
    print("2. Network routing/multicast issues")
    print("3. Different network segments")
    print("4. mDNS service not properly advertising")

if __name__ == "__main__":
    main()
