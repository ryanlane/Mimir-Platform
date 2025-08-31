#!/usr/bin/env python3
"""
Test script for scene subchannel validation
"""

import requests
import json

# API base URL
API_BASE = "http://oak:5000/api"

def test_scene_subchannel_validation():
    """Test scene validation with subchannel requirements"""
    
    print("🧪 Testing Scene Subchannel Validation")
    print("=" * 50)
    
    # Test 1: Check channel subchannel config
    print("\n1. Testing channel subchannel configuration endpoint:")
    try:
        response = requests.get(f"{API_BASE}/channels/com.epaperframe.photoframe/subchannel-config")
        if response.status_code == 200:
            config = response.json()
            print(f"   ✅ Photo frame channel config: {json.dumps(config, indent=4)}")
        else:
            print(f"   ❌ Failed to get config: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ Error getting channel config: {e}")
    
    # Test 2: Create scene with subchannel-enabled channel but no subchannel (should fail)
    print("\n2. Testing scene creation with missing subchannel (should fail):")
    try:
        scene_data = {
            "name": "Test Invalid Scene",
            "channels": [
                {"channel_id": "com.epaperframe.photoframe"}  # No subchannel_id
            ]
        }
        
        response = requests.post(f"{API_BASE}/scenes", json=scene_data)
        if response.status_code == 400:
            error_data = response.json()
            print(f"   ✅ Correctly rejected scene: {json.dumps(error_data, indent=4)}")
        else:
            print(f"   ❌ Scene should have been rejected but wasn't: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error testing invalid scene: {e}")
    
    # Test 3: Create scene with valid subchannel (should succeed)
    print("\n3. Testing scene creation with valid subchannel (should succeed):")
    try:
        scene_data = {
            "name": "Test Valid Scene",
            "channels": [
                {
                    "channel_id": "com.epaperframe.photoframe",
                    "subchannel_id": "ryans_gallery"  # Use the actual available subchannel
                }
            ]
        }
        
        response = requests.post(f"{API_BASE}/scenes", json=scene_data)
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Successfully created scene: {json.dumps(result, indent=4)}")
        else:
            print(f"   ❌ Failed to create valid scene: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error creating valid scene: {e}")
    
    # Test 4: Create scene with invalid subchannel (should fail)
    print("\n4. Testing scene creation with invalid subchannel (should fail):")
    try:
        scene_data = {
            "name": "Test Invalid Subchannel Scene",
            "channels": [
                {
                    "channel_id": "com.epaperframe.photoframe",
                    "subchannel_id": "nonexistent_gallery"
                }
            ]
        }
        
        response = requests.post(f"{API_BASE}/scenes", json=scene_data)
        if response.status_code == 400:
            error_data = response.json()
            print(f"   ✅ Correctly rejected invalid subchannel: {json.dumps(error_data, indent=4)}")
        else:
            print(f"   ❌ Should have rejected invalid subchannel: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error testing invalid subchannel: {e}")
    
    # Test 5: Create scene with mixed channels (some with subchannels, some without)
    print("\n5. Testing scene with mixed channel types:")
    try:
        scene_data = {
            "name": "Test Mixed Scene",
            "channels": [
                {
                    "channel_id": "com.epaperframe.photoframe",
                    "subchannel_id": "vacation_2024"
                },
                {
                    "channel_id": "com.example.weather"  # Assuming this doesn't support subchannels
                }
            ]
        }
        
        response = requests.post(f"{API_BASE}/scenes", json=scene_data)
        print(f"   Response: {response.status_code} - {response.text}")
        
    except Exception as e:
        print(f"   ❌ Error testing mixed scene: {e}")
    
    # Test 6: Test the channels subchannel requirements endpoint
    print("\n6. Testing channels subchannel requirements endpoint:")
    try:
        response = requests.get(f"{API_BASE}/channels/subchannel-requirements")
        if response.status_code == 200:
            requirements = response.json()
            print(f"   ✅ Channel requirements: {json.dumps(requirements, indent=4)}")
        else:
            print(f"   ❌ Failed to get requirements: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ Error getting requirements: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Scene subchannel validation test completed!")

if __name__ == "__main__":
    print("📋 Note: Make sure the Mimir API server is running on localhost:8000")
    test_scene_subchannel_validation()
