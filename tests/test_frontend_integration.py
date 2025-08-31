#!/usr/bin/env python3
"""
Test script to verify frontend integration with subchannel validation
"""

import requests
import json

API_BASE = "http://oak:5000/api"

def test_frontend_integration():
    print("🧪 Testing Frontend Integration with Subchannel Validation")
    print("=" * 60)
    
    # Test 1: Get channels and their subchannel requirements
    print("\n1. Testing channel and subchannel requirements discovery")
    
    try:
        # Get all channels
        channels_response = requests.get(f"{API_BASE}/channels")
        channels_data = channels_response.json()
        channels = channels_data.get('channels', [])
        print(f"✅ Found {len(channels)} channels")
        
        # Get subchannel requirements for all channels
        requirements_response = requests.get(f"{API_BASE}/channels/subchannel-requirements")
        requirements_data = requirements_response.json()
        channels_with_requirements = requirements_data.get('channels', [])
        print(f"✅ Retrieved subchannel requirements for {len(channels_with_requirements)} channels")
        
        for channel_info in channels_with_requirements:
            status = "REQUIRED" if channel_info['requires_subchannel'] else "OPTIONAL"
            supports = "YES" if channel_info['supports_subchannels'] else "NO"
            print(f"   - {channel_info['name']}: Supports={supports}, Required={status}")
            if channel_info['subchannels']:
                subchannel_names = [sc['name'] for sc in channel_info['subchannels']]
                print(f"     Available: {subchannel_names}")
            
    except Exception as e:
        print(f"❌ Error testing requirements discovery: {e}")
        return False
    
    # Test 2: Test specific channel subchannel config
    print("\n2. Testing individual channel subchannel config")
    
    for channel in channels:
        try:
            config_response = requests.get(f"{API_BASE}/channels/{channel['id']}/subchannel-config")
            config = config_response.json()
            
            if config.get('supports_subchannels'):
                print(f"   - {channel['name']}: Supports subchannels")
                
                # Get available subchannels
                subchannels_response = requests.get(f"{API_BASE}/channels/{channel['id']}/subchannels")
                subchannels = subchannels_response.json()
                print(f"     Available subchannels: {[sc['name'] for sc in subchannels]}")
                
        except Exception as e:
            print(f"   - {channel['name']}: No subchannel support ({e})")
    
    # Test 3: Test scene validation scenarios
    print("\n3. Testing scene validation scenarios")
    
    # Find a channel that requires subchannels
    photo_frame_channel = None
    for channel in channels:
        if channel['name'] == 'Photo Frame':
            photo_frame_channel = channel
            break
    
    if not photo_frame_channel:
        print("❌ Photo Frame channel not found for testing")
        return False
    
    # Test invalid scene (missing subchannel)
    print("\n   a) Testing invalid scene (missing required subchannel)")
    invalid_scene = {
        "name": "Test Invalid Scene",
        "channels": [
            {"channel_id": photo_frame_channel['id'], "subchannel_id": None}
        ],
        "overlay": {"overlays": [], "position": ["top", "right"], "background": True}
    }
    
    try:
        response = requests.post(f"{API_BASE}/scenes", json=invalid_scene)
        if response.status_code == 422:
            errors = response.json()['detail']
            print(f"✅ Validation correctly rejected scene: {errors}")
        else:
            print(f"❌ Expected validation error, got status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing invalid scene: {e}")
    
    # Test valid scene (with subchannel)
    print("\n   b) Testing valid scene (with required subchannel)")
    
    # Get available subchannels for photo frame
    try:
        subchannels_response = requests.get(f"{API_BASE}/channels/{photo_frame_channel['id']}/subchannels")
        subchannels = subchannels_response.json()
        
        if not subchannels:
            print("❌ No subchannels available for testing")
            return False
        
        valid_scene = {
            "name": "Test Valid Scene",
            "channels": [
                {"channel_id": photo_frame_channel['id'], "subchannel_id": subchannels[0]['id']}
            ],
            "overlay": {"overlays": [], "position": ["top", "right"], "background": True}
        }
        
        response = requests.post(f"{API_BASE}/scenes", json=valid_scene)
        if response.status_code == 201:
            scene_data = response.json()
            print(f"✅ Valid scene created successfully: {scene_data['name']}")
            
            # Clean up - delete the test scene
            scene_id = scene_data['id']
            delete_response = requests.delete(f"{API_BASE}/scenes/{scene_id}")
            if delete_response.status_code == 200:
                print("✅ Test scene cleaned up")
            
        else:
            print(f"❌ Expected success, got status {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing valid scene: {e}")
    
    print("\n🎉 Frontend integration testing completed!")
    return True

if __name__ == "__main__":
    test_frontend_integration()
