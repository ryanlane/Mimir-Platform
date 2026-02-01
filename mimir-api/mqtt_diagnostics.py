#!/usr/bin/env python3
"""
MQTT Broker Diagnostics
Helps troubleshoot MQTT connectivity issues
"""
import socket
import sys
from datetime import datetime

def test_hostname_resolution(hostname):
    """Test if hostname resolves to an IP"""
    try:
        ip = socket.gethostbyname(hostname)
        print(f"✅ Hostname '{hostname}' resolves to: {ip}")
        return ip
    except socket.gaierror as e:
        print(f"❌ Hostname '{hostname}' resolution failed: {e}")
        return None

def test_port_connectivity(hostname, port):
    """Test if we can connect to a specific port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        result = sock.connect_ex((hostname, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is open on {hostname}")
            return True
        else:
            print(f"❌ Port {port} is closed on {hostname} (error code: {result})")
            return False
    except Exception as e:
        print(f"❌ Error testing port {port} on {hostname}: {e}")
        return False

def scan_common_mqtt_ports(hostname):
    """Scan common MQTT ports"""
    common_ports = [1883, 8883, 9001, 8000, 8080]
    print(f"\n🔍 Scanning common MQTT ports on {hostname}...")
    
    open_ports = []
    for port in common_ports:
        if test_port_connectivity(hostname, port):
            open_ports.append(port)
    
    return open_ports

def main():
    hostname = "oak"
    print(f"🔧 MQTT Broker Diagnostics for '{hostname}'")
    print(f"   Timestamp: {datetime.now()}")
    print("=" * 50)
    
    # Test 1: Hostname resolution
    print(f"\n1️⃣ Testing hostname resolution...")
    ip = test_hostname_resolution(hostname)
    
    if not ip:
        print(f"\n❌ Cannot resolve hostname '{hostname}'")
        print(f"   Suggestions:")
        print(f"   - Check if 'oak' is in your /etc/hosts file")
        print(f"   - Try using the IP address directly")
        print(f"   - Check DNS configuration")
        return
    
    # Test 2: Standard MQTT port
    print(f"\n2️⃣ Testing standard MQTT port (1883)...")
    if test_port_connectivity(hostname, 1883):
        print(f"✅ MQTT broker appears to be running on standard port!")
    else:
        print(f"❌ Standard MQTT port (1883) is not accessible")
    
    # Test 3: Scan other common ports
    open_ports = scan_common_mqtt_ports(hostname)
    
    if open_ports:
        print(f"\n✅ Found {len(open_ports)} open ports: {open_ports}")
        for port in open_ports:
            if port != 1883:
                print(f"   💡 Try connecting to port {port} instead")
    else:
        print(f"\n❌ No common MQTT ports are open")
        print(f"   Suggestions:")
        print(f"   - Check if MQTT broker is running on {hostname}")
        print(f"   - Check firewall settings")
        print(f"   - Verify the correct hostname/IP")
    
    # Test 4: Additional diagnostics
    print(f"\n4️⃣ Additional diagnostics...")
    print(f"   Try these commands on {hostname}:")
    print(f"   - sudo systemctl status mosquitto")
    print(f"   - sudo netstat -tlnp | grep :1883")
    print(f"   - sudo ufw status (if using UFW firewall)")

if __name__ == "__main__":
    main()
