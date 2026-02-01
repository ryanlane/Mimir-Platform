#!/usr/bin/env python3
"""
MQTT Presence Client for Mimir Display Devices
This script should be run on display devices to maintain MQTT presence
"""
import asyncio
import json
import socket
import sys
import signal
import argparse
from datetime import datetime, timezone
from typing import Optional

try:
    from aiomqtt import Client, MqttError
    AIOMQTT_AVAILABLE = True
except ImportError:
    try:
        import paho.mqtt.client as mqtt
        PAHO_MQTT_AVAILABLE = True
        AIOMQTT_AVAILABLE = False
    except ImportError:
        print("❌ Neither aiomqtt nor paho-mqtt is available")
        print("   Install with: pip install aiomqtt")
        sys.exit(1)


class MqttPresenceClient:
    """MQTT presence client for display devices"""
    
    def __init__(self, broker_host: str, broker_port: int = 1883, 
                 device_id: Optional[str] = None, heartbeat_interval: int = 30):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.device_id = device_id or f"display-{socket.gethostname()}"
        self.heartbeat_interval = heartbeat_interval
        
        # Topics
        self.status_topic = f"mimir/{self.device_id}/status"
        self.heartbeat_topic = f"mimir/{self.device_id}/heartbeat"
        
        # Last Will & Testament
        self.lwt_payload = json.dumps({
            "status": "offline",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "unexpected_disconnect",
            "device_id": self.device_id
        })
        
        # State
        self.running = False
        self.client: Optional[Client] = None
        
        print(f"🔧 MQTT Presence Client initialized")
        print(f"   Device ID: {self.device_id}")
        print(f"   Broker: {self.broker_host}:{self.broker_port}")
        print(f"   Status Topic: {self.status_topic}")
        print(f"   Heartbeat Interval: {self.heartbeat_interval}s")
    
    async def start_async(self):
        """Start the MQTT presence client (asyncio version)"""
        if not AIOMQTT_AVAILABLE:
            raise RuntimeError("asyncio-mqtt not available")
        
        self.running = True
        
        while self.running:
            try:
                # Connect with Last Will & Testament
                async with Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    identifier=self.device_id,  # Changed from client_id to identifier
                    # Note: Will configuration moved in v1.0 - would need separate setup
                ) as client:
                    self.client = client
                    
                    # Publish that we're online
                    online_payload = json.dumps({
                        "status": "online",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "device_id": self.device_id,
                        "hostname": socket.gethostname(),
                        "heartbeat_interval": self.heartbeat_interval
                    })
                    
                    await client.publish(self.status_topic, online_payload, qos=1, retain=True)
                    print(f"✅ Connected to MQTT broker - published online status")
                    
                    # Start heartbeat loop
                    while self.running:
                        try:
                            # Send heartbeat
                            heartbeat_payload = json.dumps({
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "device_id": self.device_id,
                                "uptime": "unknown"  # Could add actual uptime here
                            })
                            
                            await client.publish(self.heartbeat_topic, heartbeat_payload, qos=0)
                            print(f"💓 Heartbeat sent at {datetime.now().strftime('%H:%M:%S')}")
                            
                            # Wait for next heartbeat
                            await asyncio.sleep(self.heartbeat_interval)
                            
                        except asyncio.CancelledError:
                            break
                        except Exception as e:
                            print(f"❌ Error in heartbeat loop: {e}")
                            break
                    
            except MqttError as e:
                print(f"❌ MQTT connection error: {e}")
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
            
            if self.running:
                print("🔄 Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    def start_sync(self):
        """Start the MQTT presence client (paho-mqtt version)"""
        if not PAHO_MQTT_AVAILABLE:
            raise RuntimeError("paho-mqtt not available")
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                # Publish online status
                online_payload = json.dumps({
                    "status": "online",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "device_id": self.device_id,
                    "hostname": socket.gethostname(),
                    "heartbeat_interval": self.heartbeat_interval
                })
                client.publish(self.status_topic, online_payload, qos=1, retain=True)
                print(f"✅ Connected to MQTT broker - published online status")
            else:
                print(f"❌ Failed to connect to MQTT broker: {rc}")
        
        def on_disconnect(client, userdata, rc):
            print(f"🔌 Disconnected from MQTT broker")
        
        # Create client
        client = mqtt.Client(client_id=self.device_id, clean_session=True)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        # Set Last Will & Testament
        client.will_set(self.status_topic, self.lwt_payload, qos=1, retain=True)
        
        # Connect to broker
        try:
            client.connect(self.broker_host, self.broker_port, keepalive=60)
            client.loop_start()
            
            self.running = True
            print(f"🚀 MQTT presence client started")
            
            # Heartbeat loop
            while self.running:
                try:
                    heartbeat_payload = json.dumps({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "device_id": self.device_id,
                        "uptime": "unknown"
                    })
                    
                    client.publish(self.heartbeat_topic, heartbeat_payload, qos=0)
                    print(f"💓 Heartbeat sent at {datetime.now().strftime('%H:%M:%S')}")
                    
                    import time
                    time.sleep(self.heartbeat_interval)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error in heartbeat loop: {e}")
                    
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            return
        finally:
            # Graceful shutdown
            if client.is_connected():
                offline_payload = json.dumps({
                    "status": "offline",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": "graceful_shutdown",
                    "device_id": self.device_id
                })
                client.publish(self.status_topic, offline_payload, qos=1, retain=True)
                print(f"📤 Published graceful offline status")
                
            client.loop_stop()
            client.disconnect()
            print(f"🛑 MQTT presence client stopped")
    
    def stop(self):
        """Stop the presence client"""
        self.running = False


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\n🛑 Received signal {signum} - shutting down gracefully...")
    global presence_client
    if presence_client:
        presence_client.stop()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="MQTT Presence Client for Mimir Display Devices")
    parser.add_argument("--broker", "-b", default="localhost", help="MQTT broker hostname")
    parser.add_argument("--port", "-p", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--device-id", "-d", help="Device ID (default: display-<hostname>)")
    parser.add_argument("--heartbeat", "-t", type=int, default=30, help="Heartbeat interval in seconds")
    parser.add_argument("--sync", action="store_true", help="Use synchronous paho-mqtt instead of asyncio-mqtt")
    
    args = parser.parse_args()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    global presence_client
    presence_client = MqttPresenceClient(
        broker_host=args.broker,
        broker_port=args.port,
        device_id=args.device_id,
        heartbeat_interval=args.heartbeat
    )
    
    try:
        if args.sync or not AIOMQTT_AVAILABLE:
            print("🔄 Using synchronous paho-mqtt client")
            presence_client.start_sync()
        else:
            print("🔄 Using asynchronous asyncio-mqtt client")
            asyncio.run(presence_client.start_async())
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
