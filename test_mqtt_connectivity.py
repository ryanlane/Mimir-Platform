#!/usr/bin/env python3
"""
MQTT Connectivity Test for Mimir
Tests basic MQTT broker connectivity before deploying presence system
"""
import asyncio
import json
import socket
from datetime import datetime, timezone
from aiomqtt import Client, MqttError


async def test_mqtt_connectivity(broker_host="oak", broker_port=1883):
    """Test basic MQTT connectivity"""
    device_id = f"test-client-{socket.gethostname()}"
    test_topic = f"mimir/test/{device_id}"
    
    print(f"🔧 Testing MQTT connectivity")
    print(f"   Broker: {broker_host}:{broker_port}")
    print(f"   Device ID: {device_id}")
    print(f"   Test Topic: {test_topic}")
    
    try:
        # Test connection with Last Will & Testament
        lwt_payload = json.dumps({
            "status": "test_disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": device_id
        })
        
        async with Client(
            hostname=broker_host,
            port=broker_port,
            client_id=device_id,
            will=(test_topic, lwt_payload, 1, True)  # QoS=1, Retain=True
        ) as client:
            print(f"✅ Successfully connected to MQTT broker")
            
            # Subscribe to our test topic to see our own messages
            await client.subscribe(test_topic)
            print(f"✅ Subscribed to test topic")
            
            # Publish a test message
            test_payload = json.dumps({
                "status": "test_online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_id": device_id,
                "message": "MQTT connectivity test successful"
            })
            
            await client.publish(test_topic, test_payload, qos=1, retain=True)
            print(f"✅ Published test message")
            
            # Try to receive the message
            print(f"🔄 Waiting for message confirmation...")
            try:
                async with asyncio.timeout(5):  # 5 second timeout
                    async for message in client.messages:
                        received_data = json.loads(message.payload.decode())
                        print(f"✅ Received message: {received_data.get('message', 'No message')}")
                        print(f"   Status: {received_data.get('status')}")
                        print(f"   Timestamp: {received_data.get('timestamp')}")
                        break
            except asyncio.TimeoutError:
                print(f"⚠️  Did not receive message within timeout (broker may not support message loopback)")
            
            # Clean up - publish offline status
            cleanup_payload = json.dumps({
                "status": "test_offline",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_id": device_id,
                "message": "Test completed successfully"
            })
            await client.publish(test_topic, cleanup_payload, qos=1, retain=True)
            print(f"✅ Published cleanup message")
            
        print(f"🎉 MQTT connectivity test completed successfully!")
        return True
        
    except MqttError as e:
        print(f"❌ MQTT Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


async def test_mimir_presence_topics():
    """Test the specific topics that Mimir presence system will use"""
    device_id = "test-display"
    broker_host = "oak"
    
    print(f"\n🔧 Testing Mimir presence topics")
    
    status_topic = f"mimir/{device_id}/status"
    heartbeat_topic = f"mimir/{device_id}/heartbeat"
    
    try:
        async with Client(hostname=broker_host, client_id=f"{device_id}-test") as client:
            # Test status topic
            status_payload = json.dumps({
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_id": device_id,
                "hostname": socket.gethostname()
            })
            await client.publish(status_topic, status_payload, qos=1, retain=True)
            print(f"✅ Published to status topic: {status_topic}")
            
            # Test heartbeat topic
            heartbeat_payload = json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_id": device_id
            })
            await client.publish(heartbeat_topic, heartbeat_payload, qos=0)
            print(f"✅ Published to heartbeat topic: {heartbeat_topic}")
            
            # Test offline status
            offline_payload = json.dumps({
                "status": "offline",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_id": device_id,
                "reason": "test_completed"
            })
            await client.publish(status_topic, offline_payload, qos=1, retain=True)
            print(f"✅ Published offline status")
            
        print(f"🎉 Mimir presence topics test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing Mimir topics: {e}")
        return False


async def main():
    """Run all MQTT tests"""
    print("🚀 Starting MQTT connectivity tests for Mimir\n")
    
    # Test 1: Basic connectivity
    basic_test = await test_mqtt_connectivity()
    
    if basic_test:
        # Test 2: Mimir-specific topics
        mimir_test = await test_mimir_presence_topics()
        
        if mimir_test:
            print(f"\n🎉 All MQTT tests passed! Your broker is ready for Mimir presence system.")
            print(f"\nNext steps:")
            print(f"1. Update your mimir-api config.py with correct MQTT broker settings")
            print(f"2. Install mqtt_presence_client.py on your display devices")
            print(f"3. Restart the mimir-api service to enable MQTT presence")
        else:
            print(f"\n❌ Mimir topic tests failed")
    else:
        print(f"\n❌ Basic MQTT connectivity failed")
        print(f"   Please check your MQTT broker configuration")


if __name__ == "__main__":
    asyncio.run(main())
