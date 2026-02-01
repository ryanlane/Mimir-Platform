#!/usr/bin/env python3
"""
MQTT Message Monitor
Monitor all MQTT messages on Mimir topics to verify presence system
"""
import asyncio
import json
from datetime import datetime
from aiomqtt import Client

async def monitor_mqtt_messages(broker_host="oak", broker_port=1883):
    """Monitor all Mimir MQTT messages"""
    print(f"🔍 MQTT Message Monitor")
    print(f"   Broker: {broker_host}:{broker_port}")
    print(f"   Monitoring topic: mimir/#")
    print(f"   Started: {datetime.now()}")
    print("=" * 60)
    
    try:
        async with Client(hostname=broker_host, port=broker_port, identifier="mimir-monitor") as client:
            # Subscribe to all Mimir topics
            await client.subscribe("mimir/#")
            print(f"✅ Subscribed to mimir/#")
            print(f"🔄 Waiting for messages...\n")
            
            async for message in client.messages:
                try:
                    # Parse message
                    topic = message.topic.value
                    payload = message.payload.decode()
                    
                    # Try to parse as JSON
                    try:
                        data = json.loads(payload)
                        formatted_payload = json.dumps(data, indent=2)
                    except:
                        formatted_payload = payload
                    
                    # Display message
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"📨 [{timestamp}] {topic}")
                    print(f"   {formatted_payload}")
                    print("-" * 40)
                    
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    
    except KeyboardInterrupt:
        print(f"\n🛑 Monitor stopped by user")
    except Exception as e:
        print(f"❌ Monitor error: {e}")

if __name__ == "__main__":
    asyncio.run(monitor_mqtt_messages())
