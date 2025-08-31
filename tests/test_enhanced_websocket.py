#!/usr/bin/env python3
"""
Enhanced WebSocket client to test new features
"""
import asyncio
import websockets
import json

async def test_enhanced_websocket():
    uri = "ws://localhost:5000/ws"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to Enhanced WebSocket!")
            
            # Listen for messages
            print("🔊 Listening for enhanced events... (Press Ctrl+C to stop)")
            message_count = 0
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_count += 1
                    
                    print(f"\n📨 Message #{message_count}")
                    print(f"🚀 Event: {data['event']}")
                    print(f"📊 Sequence ID: {data.get('sequenceId', 'N/A')}")
                    print(f"⏰ Timestamp: {data['timestamp']}")
                    
                    # Show different details based on event type
                    if data['event'] == 'connection_established':
                        print("🔗 CONNECTION ESTABLISHED!")
                        current_state = data['data']['currentState']
                        print(f"   Active Scenes: {current_state['activeScenes']}")
                        print(f"   Total Scenes: {len(current_state['allScenes'])}")
                        print(f"   Channels: {len(current_state['channels'])}")
                        print(f"   Current Scene: {current_state['displayStatus']['currentScene']}")
                        
                    elif data['event'] in ['scene_activated', 'scene_deactivated']:
                        event_data = data['data']
                        print(f"   Scene: {event_data['sceneName']} ({event_data['sceneId']})")
                        if 'previousScene' in event_data and event_data['previousScene']:
                            print(f"   Previous: {event_data['previousSceneName']} ({event_data['previousScene']})")
                        print(f"   Channels: {event_data.get('channels', [])}")
                        
                    elif data['event'] == 'channel_status_update':
                        event_data = data['data']
                        print(f"   Channel: {event_data['channelName']} ({event_data['channelId']})")
                        print(f"   Status: {json.dumps(event_data['status'], indent=6)}")
                        
                    elif data['event'] == 'ping':
                        print("💓 Heartbeat ping received")
                        # Send pong response
                        pong = {
                            "event": "pong",
                            "data": {"timestamp": data['data']['timestamp']}
                        }
                        await websocket.send(json.dumps(pong))
                        print("💓 Pong sent")
                        
                    else:
                        print(f"   Data: {json.dumps(data['data'], indent=6)}")
                    
                    print("─" * 60)
                    
                    # Test heartbeat every 5 messages
                    if message_count % 5 == 0:
                        ping = {
                            "event": "ping",
                            "data": {"timestamp": "client-ping"}
                        }
                        await websocket.send(json.dumps(ping))
                        print("💓 Sent client ping")
                        
                except json.JSONDecodeError:
                    print(f"📨 Raw message: {message}")
                    
    except websockets.exceptions.ConnectionRefused:
        print("❌ Failed to connect. Is the server running on localhost:5000?")
    except KeyboardInterrupt:
        print("\n👋 Disconnected from Enhanced WebSocket")

if __name__ == "__main__":
    asyncio.run(test_enhanced_websocket())
