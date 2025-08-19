# WebSocket Enhancement Recommendations for Mimir Platform API

Based on the current WebSocket implementation and frontend requirements, here are key improvements that would enhance the real-time experience and state management.

## Current Issues & Gaps

### 1. **State Synchronization**
- WebSocket events provide notifications but don't guarantee state consistency
- Clients may miss events during disconnection/reconnection
- No way to request current state snapshot via WebSocket

### 2. **Event Data Completeness**
- Scene activation events may not include complete scene information
- Missing context about what triggered the event
- No user/session information for multi-user scenarios

### 3. **Connection Management**
- No heartbeat/ping mechanism for connection health
- No graceful handling of connection drops
- Missing connection status events

## Recommended Enhancements

### 1. **Full State Broadcast on Connection**
When a client connects to the WebSocket, send the complete current state:

```json
{
  "event": "connection_established",
  "data": {
    "connectionId": "uuid-here",
    "currentState": {
      "displayStatus": {
        "currentScene": "evening-gallery",
        "currentImage": { /* full image info */ },
        "hardware": { /* hardware status */ }
      },
      "activeScenes": ["evening-gallery"],
      "channels": [
        {
          "id": "weather_channel", 
          "status": "active",
          "lastUpdate": "2025-08-19T10:30:00Z"
        }
      ]
    },
    "timestamp": "2025-08-19T10:30:00Z"
  }
}
```

### 2. **Enhanced Event Data Structure**
Standardize all WebSocket events with rich context:

```json
{
  "event": "scene_activated",
  "data": {
    "sceneId": "evening-gallery",
    "sceneName": "Evening Gallery",
    "previousScene": "morning-weather",
    "triggeredBy": {
      "source": "api",
      "userId": "admin",
      "timestamp": "2025-08-19T10:30:00Z"
    },
    "displayUpdate": {
      "currentImage": { /* full image info */ },
      "resolution": [800, 600]
    }
  },
  "timestamp": "2025-08-19T10:30:00Z",
  "sequenceId": 12345
}
```

### 3. **State Reconciliation Events**
Add events for maintaining state consistency:

```json
{
  "event": "state_sync_request",
  "data": {
    "lastKnownSequenceId": 12340
  }
}
```

Response:
```json
{
  "event": "state_sync_response", 
  "data": {
    "currentState": { /* full state */ },
    "missedEvents": [
      { /* events since lastKnownSequenceId */ }
    ],
    "currentSequenceId": 12345
  }
}
```

### 4. **Connection Health & Heartbeat**
Implement ping/pong mechanism for connection monitoring:

```json
{
  "event": "ping",
  "data": {
    "timestamp": "2025-08-19T10:30:00Z"
  }
}
```

Expected response:
```json
{
  "event": "pong", 
  "data": {
    "timestamp": "2025-08-19T10:30:00Z"
  }
}
```

### 5. **Batch Events for Efficiency**
For rapid state changes, batch events to reduce message volume:

```json
{
  "event": "batch_update",
  "data": {
    "events": [
      {
        "event": "scene_deactivated",
        "data": { "sceneId": "morning-weather" }
      },
      {
        "event": "scene_activated", 
        "data": { "sceneId": "evening-gallery" }
      }
    ],
    "finalState": {
      "currentScene": "evening-gallery"
    }
  },
  "timestamp": "2025-08-19T10:30:00Z"
}
```

### 6. **Error Handling & Recovery**
Add error events and recovery mechanisms:

```json
{
  "event": "error",
  "data": {
    "code": "SCENE_ACTIVATION_FAILED",
    "message": "Failed to activate scene: hardware unavailable",
    "sceneId": "evening-gallery",
    "recovery": {
      "action": "retry_after_delay",
      "delaySeconds": 5
    }
  }
}
```

### 7. **Channel Status Updates**
Real-time channel monitoring:

```json
{
  "event": "channel_status_update",
  "data": {
    "channelId": "weather_channel",
    "status": {
      "active": true,
      "lastUpdate": "2025-08-19T10:30:00Z",
      "usingFallback": false,
      "lastError": null,
      "imageGenerated": true
    }
  }
}
```

### 8. **Display Hardware Events**
Monitor hardware status changes:

```json
{
  "event": "display_hardware_update",
  "data": {
    "hardware": {
      "available": false,
      "type": "waveshare",
      "resolution": [800, 600],
      "lastError": "Connection timeout"
    },
    "impact": {
      "currentScene": "evening-gallery",
      "fallbackActive": true
    }
  }
}
```

### 9. **User Session Management**
For multi-user scenarios:

```json
{
  "event": "user_connected",
  "data": {
    "userId": "admin",
    "sessionId": "session-uuid",
    "permissions": ["scene_management", "display_control"]
  }
}
```

### 10. **Subscription Management**
Allow clients to subscribe to specific event types:

```json
{
  "event": "subscribe",
  "data": {
    "events": ["scene_activated", "scene_deactivated", "display_update"],
    "options": {
      "includeHistory": false,
      "batchUpdates": true
    }
  }
}
```

## Implementation Priority

### High Priority (Immediate Benefits)
1. **Full state broadcast on connection** - Fixes state persistence issues
2. **Enhanced event data structure** - Provides complete context
3. **Heartbeat mechanism** - Improves connection reliability

### Medium Priority (Enhanced UX)
4. **State reconciliation** - Handles missed events
5. **Channel status updates** - Real-time monitoring
6. **Error handling** - Better error recovery

### Low Priority (Advanced Features)
7. **Batch events** - Performance optimization
8. **User session management** - Multi-user support
9. **Subscription management** - Flexible event filtering

## Current Frontend Impact

With these enhancements, the frontend could:

- **Eliminate polling** - No need for periodic API calls
- **Instant state recovery** - Reconnecting clients get immediate state sync
- **Better error handling** - Display meaningful error messages
- **Real-time everything** - All changes propagate instantly
- **Offline resilience** - Handle connection drops gracefully
- **Multi-tab sync** - Perfect synchronization across browser tabs

## Backward Compatibility

These changes should be implemented as additive features to maintain compatibility with the current WebSocket implementation. Existing event formats should continue to work while new enhanced formats are introduced alongside them.

---

## ✅ Implementation Status (August 19, 2025)

### ✅ **High Priority - COMPLETED**
- ✅ **Full state broadcast on connection** - Complete application state sent immediately on connect
- ✅ **Enhanced event data structure** - Rich context with triggeredBy, previousState, and sequence IDs  
- ✅ **Heartbeat mechanism** - Ping/pong support for connection health monitoring

### ✅ **Medium Priority - COMPLETED**
- ✅ **Channel status updates** - Real-time channel monitoring with detailed status info
- ✅ **Error handling events** - Structured error broadcasting with recovery suggestions
- ✅ **Display hardware events** - Real-time display status updates

### 🔄 **Partially Implemented**
- 🔄 **State reconciliation** - Basic state sync request/response (client can request full state)
- 🔄 **Subscription management** - Basic subscription confirmation (foundation in place)

### 📋 **Remaining Enhancements**
- ⏳ **Batch events** - Performance optimization for rapid state changes
- ⏳ **User session management** - Multi-user support with permissions
- ⏳ **Advanced subscription filtering** - Granular event filtering

### 🎯 **Frontend Impact Achieved**
- ✅ **Eliminated polling** - No need for periodic API calls
- ✅ **Instant state recovery** - Reconnecting clients get immediate complete state
- ✅ **Better error handling** - Real-time error notifications with context
- ✅ **Real-time everything** - All changes propagate instantly with rich context
- ✅ **Connection resilience** - Heartbeat monitoring and health checking
- ✅ **Perfect multi-tab sync** - Complete state synchronization across browser tabs

The enhanced WebSocket implementation now provides enterprise-grade real-time functionality with comprehensive state management, error handling, and connection monitoring.
