#!/usr/bin/env python3

"""
Simple mDNS discovery test without zeroconf dependency
"""

import subprocess
import sys
import json

def test_with_avahi():
    """Test discovery using avahi-browse"""
    try:
        print("🔍 Testing mDNS discovery with avahi-browse...")
        result = subprocess.run(
            ["avahi-browse", "-r", "_mimir-display._tcp", "-t"],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        print("Raw avahi output:")
        print(result.stdout)
        print("---")
        
        if "_mimir-display._tcp" in result.stdout:
            print("✅ Found mimir display service!")
            return True
        else:
            print("❌ No mimir display services found")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏱️ Discovery timeout")
        return False
    except FileNotFoundError:
        print("❌ avahi-browse not available")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_with_dig():
    """Test discovery using dig"""
    try:
        print("🔍 Testing mDNS with dig...")
        result = subprocess.run(
            ["dig", "@224.0.0.251", "-p", "5353", "_mimir-display._tcp.local.", "PTR"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print("Raw dig output:")
        print(result.stdout)
        print("---")
        
        if "_mimir-display._tcp" in result.stdout:
            print("✅ Found mimir display service via dig!")
            return True
        else:
            print("❌ No mimir display services found via dig")
            return False
            
    except Exception as e:
        print(f"❌ Error with dig: {e}")
        return False

def main():
    print("🧪 Simple mDNS Discovery Test")
    print("=" * 40)
    
    found_avahi = test_with_avahi()
    print()
    found_dig = test_with_dig()
    
    print()
    print("📊 Summary:")
    print(f"  Avahi: {'✅ Found' if found_avahi else '❌ Not found'}")
    print(f"  Dig:   {'✅ Found' if found_dig else '❌ Not found'}")
    
    if found_avahi or found_dig:
        print("\n🎉 Display is advertising via mDNS!")
        print("The issue is likely that the API server doesn't have the zeroconf library installed.")
    else:
        print("\n⚠️ Display not found via mDNS")
        print("Check that the display client is running in discovery mode.")

if __name__ == "__main__":
    main()
