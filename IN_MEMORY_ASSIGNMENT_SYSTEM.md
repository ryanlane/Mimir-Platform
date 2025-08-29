# In-Memory Assignment System for Discovered Displays

## Overview

The Mimir API now supports **in-memory assignments** for discovered displays, implementing a hybrid approach that handles both registered displays (stored in database) and discovered displays (ephemeral, in-memory storage).

## Architecture Design

### 🏛️ **Dual Assignment System**

#### **Registered Displays** (Database Storage)
- **Persistent assignments** stored in `display_clients.assigned_scene_id`
- **Stable, long-term** assignments that survive API restarts
- **Full database features** including history, relationships, and queries
- **Use case**: Fixed installations, kiosks, permanent displays

#### **Discovered Displays** (In-Memory Storage)
- **Ephemeral assignments** stored in memory via `DiscoveredDisplayAssignmentManager`
- **Dynamic assignments** that reset when API restarts
- **Auto-cleanup** when displays go offline or disappear
- **Use case**: Mobile devices, temporary displays, dynamic environments

## Key Components

### 📱 **DiscoveredDisplayAssignmentManager**

Thread-safe in-memory manager for discovered display assignments:

```python
# Global instance available throughout the application
from app.core.services.discovered_display_manager import discovered_assignment_manager

# Assign scene to discovered display
discovered_assignment_manager.assign_scene("display-id", "scene-id")

# Get assignment
scene_id = discovered_assignment_manager.get_assigned_scene("display-id")

# Bulk assignment
result = discovered_assignment_manager.bulk_assign_scene(
    ["display-1", "display-2"], 
    "emergency-scene"
)
```

### 🔄 **Enhanced DisplaySceneService**

Unified service that handles both display types transparently:

```python
# Works for both registered and discovered displays
service.assign_scene_to_display("any-display-id", "scene-id")

# Automatically detects display type and routes appropriately
# - Registered displays → Database storage
# - Discovered displays → In-memory storage
```

## API Endpoints

### 🔗 **Universal Assignment Endpoints**

These work for **both** registered and discovered displays:

#### Assign Scene (Universal)
```http
POST /api/displays/{display_id}/assign_scene
Content-Type: application/json

{
  "sceneId": "my-scene-id"
}
```

**Response for Discovered Display:**
```json
{
  "display_id": "discovery-colorframe05-1756316347",
  "display_name": "Inky ePaper Display",
  "display_type": "discovered",
  "scene_id": "gallery-scene",
  "scene_name": "Gallery Birds",
  "previous_scene_id": null,
  "assigned_at": "2025-08-29T22:15:30Z",
  "success": true
}
```

#### Enhanced Scene Information
```http
GET /api/scenes/{scene_id}/displays
```

**Response with Both Display Types:**
```json
{
  "scene_id": "gallery-scene",
  "scene_name": "Gallery Birds",
  "display_stats": {
    "total_assigned": 3,
    "online_displays": 2,
    "offline_displays": 1,
    "registered_displays": {
      "total": 1,
      "online": 1,
      "offline": 0
    },
    "discovered_displays": {
      "total": 2,
      "online": 1,
      "offline": 1
    }
  },
  "assigned_displays": [
    {
      "display_id": "registered-display-1",
      "display_name": "Conference Room A",
      "display_type": "registered",
      "location": "Building A",
      "is_online": true
    },
    {
      "display_id": "discovery-colorframe05-1756316347",
      "display_name": "Inky ePaper Display",
      "display_type": "discovered",
      "location": "Lab Bench",
      "is_online": true
    }
  ]
}
```

### 📱 **Discovered Display Specific Endpoints**

#### Get All Discovered Display Assignments
```http
GET /api/discovered-displays/assignments
```

#### Bulk Assign Discovered Displays
```http
POST /api/discovered-displays/assignments/bulk
Content-Type: application/json

{
  "displayIds": ["discovery-display-1", "discovery-display-2"],
  "sceneId": "emergency-scene",
  "overridePrevious": true
}
```

#### Get Unassigned Discovered Displays
```http
GET /api/discovered-displays/unassigned
```

#### Clean Up Stale Assignments
```http
POST /api/discovered-displays/cleanup
```

### 📊 **Enhanced Statistics**

#### Comprehensive Assignment Overview
```http
GET /api/display-scene/dashboard/overview
```

**Response includes both display types:**
```json
{
  "summary": {
    "total_scenes": 5,
    "total_assigned_displays": 8,
    "total_online_displays": 6,
    "total_unassigned_displays": 2,
    "registered_displays": {
      "total": 3,
      "assigned": 2,
      "unassigned": 1
    },
    "discovered_displays": {
      "total": 5,
      "assigned": 3,
      "unassigned": 2
    }
  }
}
```

## Usage Examples

### 🚀 **Quick Start: Assign Discovered Display**

```bash
# 1. Discover available displays
curl http://oak:5000/api/displays | jq '.data[] | select(.displayType == "discovered")'

# 2. Assign scene to discovered display (same endpoint as registered displays!)
curl -X POST http://oak:5000/api/displays/discovery-colorframe05-1756316347/assign_scene \
  -H "Content-Type: application/json" \
  -d '{"sceneId": "0ab5a4d5-6b5f-4a38-8cfb-3eba1eabc1db"}'

# 3. Verify assignment
curl http://oak:5000/api/scenes/0ab5a4d5-6b5f-4a38-8cfb-3eba1eabc1db/displays
```

### 📋 **Management Workflows**

#### Emergency Scene Broadcast
```bash
# Get all displays (both types)
ALL_DISPLAYS=$(curl -s http://oak:5000/api/displays | jq -r '.data[].id')

# Assign emergency scene to all discovered displays
curl -X POST http://oak:5000/api/discovered-displays/assignments/bulk \
  -H "Content-Type: application/json" \
  -d "{
    \"displayIds\": [\"discovery-display-1\", \"discovery-display-2\"],
    \"sceneId\": \"emergency-alert\"
  }"
```

#### Health Check and Cleanup
```bash
# Check assignment statistics
curl http://oak:5000/api/discovered-displays/stats

# Clean up stale assignments
curl -X POST http://oak:5000/api/discovered-displays/cleanup

# Get unassigned discovered displays
curl http://oak:5000/api/discovered-displays/unassigned
```

## Automatic Management

### 🧹 **Automatic Cleanup**

The system automatically handles:

1. **Stale Assignment Detection**: Discovers when displays go offline
2. **Memory Management**: Removes assignments for disappeared displays
3. **Thread Safety**: Concurrent access protection with RLock
4. **Logging**: Comprehensive logging of assignment changes

### 🔄 **Lifecycle Management**

```
Discovery Phase:
├── mDNS discovers display
├── Display appears in /api/displays (displayType: "discovered")
├── Display available for assignment
└── Assignment stored in memory

Active Phase:
├── Display receives scene assignments
├── Assignments tracked in memory
├── Statistics include discovered displays
└── Management via API endpoints

Cleanup Phase:
├── Display goes offline/disappears
├── Automatic cleanup removes stale assignments
├── Memory freed
└── Statistics updated
```

## Integration Benefits

### 🔄 **Seamless Operation**

1. **Unified API**: Same endpoints work for both display types
2. **Transparent Handling**: Service layer automatically detects display type
3. **Consistent Response Format**: Same response structure regardless of display type
4. **Mixed Statistics**: Combined metrics for comprehensive overview

### 🏗️ **Architecture Benefits**

1. **Separation of Concerns**: Database for persistent, memory for ephemeral
2. **Performance**: In-memory operations for dynamic assignments
3. **Scalability**: No database overhead for temporary displays
4. **Reliability**: Registered displays unaffected by discovered display changes

### 🛠️ **Developer Experience**

1. **Single API**: No need to track display types in client code
2. **Automatic Detection**: Service layer handles routing automatically
3. **Comprehensive Stats**: Full picture of all assignments
4. **Easy Testing**: Clear separation for unit testing

## Migration from Previous System

### ✅ **Backward Compatibility**

- All existing registered display functionality unchanged
- Database schema remains the same
- Existing API endpoints continue to work
- No breaking changes for current integrations

### 🆕 **New Capabilities**

- Discovered displays can now be assigned scenes
- Combined statistics and reporting
- Bulk operations for discovered displays
- Automatic cleanup and memory management

## Best Practices

### 🎯 **When to Use Each Type**

#### Use **Registered Displays** for:
- Permanent installations (kiosks, lobby displays)
- Displays requiring persistent assignments
- Displays needing full database features
- Critical displays requiring guaranteed assignment persistence

#### Use **Discovered Displays** for:
- Temporary or mobile displays
- Development and testing environments
- Dynamic display environments
- Displays that frequently appear/disappear

### 🔧 **Operational Guidelines**

1. **Regular Cleanup**: Call cleanup endpoint periodically
2. **Monitor Statistics**: Use stats endpoints for health monitoring
3. **Assignment Verification**: Check assignments after API restarts
4. **Emergency Procedures**: Use bulk assignment for rapid response

This in-memory assignment system provides the perfect balance between persistence for stable displays and flexibility for dynamic environments, ensuring your Mimir deployment can handle both fixed installations and dynamic discovery scenarios effectively.
