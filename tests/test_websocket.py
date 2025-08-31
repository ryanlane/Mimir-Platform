#!/usr/bin/env python3
"""
Simple WebSocket client to test real-time events
"""
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:5000/ws"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket!")
            
            # Listen for messages
            print("🔊 Listening for events... (Press Ctrl+C to stop)")
            async for message in websocket:
                try:
                    data = json.loads(message)
                    print(f"📨 Received event:")
                    print(f"   Event: {data['event']}")
                    print(f"   Data: {json.dumps(data['data'], indent=2)}")
                    print(f"   Timestamp: {data['timestamp']}")
                    print("-" * 50)
                except json.JSONDecodeError:
                    print(f"📨 Raw message: {message}")
                    
    except websockets.exceptions.ConnectionRefused:
        print("❌ Failed to connect. Is the server running on localhost:5000?")
    except KeyboardInterrupt:
        print("\n👋 Disconnected from WebSocket")

if __name__ == "__main__":
    asyncio.run(test_websocket())
