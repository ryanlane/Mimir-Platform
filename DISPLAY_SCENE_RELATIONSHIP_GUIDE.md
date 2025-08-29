# Enhanced Display-Scene Relationship System

## Overview

This document outlines the enhanced system for connecting discoverable displays to scenes in the Mimir API. The system provides comprehensive management of display-scene assignments with detailed statistics and bulk operations.

## Key Features

### 🔗 **Display-Scene Assignment**
- **One-to-One Relationship**: Each display can be assigned to exactly one scene at a time
- **Database Storage**: Assignments are stored in the `display_clients.assigned_scene_id` field
- **Automatic Discovery Integration**: Both manually registered and auto-discovered displays can be assigned
- **Override Support**: Previous assignments can be overridden when reassigning scenes

### 📊 **Display Statistics for Scenes**
- **Display Count**: Each scene shows how many displays are assigned to it
- **Online/Offline Status**: Track how many assigned displays are currently online
- **Location Grouping**: View displays grouped by their physical location
- **Real-time Updates**: Statistics update based on display connectivity status

### 🎯 **Enhanced API Endpoints**

## API Reference

### Core Assignment Endpoints

#### Assign Scene to Display
```http
POST /api/displays/{display_id}/assign_scene
Content-Type: application/json

{
  "sceneId": "my-scene-id"
}
```

#### Enhanced Assignment with Options
```http
POST /api/display-scene/assignments/{display_id}
Content-Type: application/json

{
  "sceneId": "my-scene-id",
  "overrideSettings": {
    "priority": 1,
    "customConfig": {}
  }
}
```

#### Unassign Scene from Display
```http
DELETE /api/displays/{display_id}/assign_scene
```

### Scene Information with Display Data

#### Get Scene with Display Statistics
```http
GET /api/scenes/{scene_id}/displays
```

**Response:**
```json
{
  "scene_id": "my-scene",
  "scene_name": "Gallery Scene",
  "display_stats": {
    "total_assigned": 5,
    "online_displays": 4,
    "offline_displays": 1
  },
  "assigned_displays": [
    {
      "id": "display-1",
      "name": "Lobby Display",
      "location": "Main Entrance",
      "is_online": true,
      "last_seen": "2025-08-29T10:30:00Z",
      "resolution": "1920x1080"
    }
  ]
}
```

#### Get All Scenes with Display Counts
```http
GET /api/display-scene/scenes/with-displays
```

**Response:**
```json
[
  {
    "id": "scene-1",
    "name": "Morning Gallery",
    "is_active": true,
    "distribution_mode": "MIRROR",
    "display_stats": {
      "total_assigned": 3,
      "online_displays": 2,
      "offline_displays": 1,
      "last_updated": "2025-08-29T10:30:00Z"
    }
  }
]
```

### Bulk Operations

#### Bulk Scene Assignment
```http
POST /api/display-scene/assignments/bulk
Content-Type: application/json

{
  "displayIds": ["display-1", "display-2", "display-3"],
  "sceneId": "emergency-scene",
  "overridePrevious": true
}
```

**Response:**
```json
{
  "successful_assignments": ["display-1", "display-2"],
  "failed_assignments": [
    {
      "display_id": "display-3",
      "error": "Display not found"
    }
  ],
  "total_processed": 3,
  "success_count": 2,
  "error_count": 1
}
```

#### Reassign Displays Between Scenes
```http
POST /api/display-scene/assignments/reassign?old_scene_id=scene-1&new_scene_id=scene-2
```

### Management and Discovery

#### Get Displays by Location
```http
GET /api/display-scene/displays/by-location
```

**Response:**
```json
[
  {
    "location": "Building A - Floor 1",
    "display_count": 4,
    "displays": [...],
    "dominant_scene": "lobby-scene",
    "scene_distribution": {
      "lobby-scene": 3,
      "info-scene": 1
    }
  }
]
```

#### Get Unassigned Displays
```http
GET /api/display-scene/displays/unassigned
```

**Response:**
```json
{
  "total_unassigned": 2,
  "displays": [
    {
      "display_id": "new-display-1",
      "display_name": "Conference Room B",
      "location": "Building B",
      "is_online": true,
      "discovery_method": "mdns",
      "auto_discovered": true
    }
  ]
}
```

#### Assignment Dashboard
```http
GET /api/display-scene/dashboard/overview
```

**Response:**
```json
{
  "summary": {
    "total_scenes": 5,
    "total_assigned_displays": 12,
    "total_online_displays": 10,
    "total_unassigned_displays": 3,
    "total_locations": 4
  },
  "scenes_with_displays": [...],
  "unassigned_displays": [...],
  "location_groups": [...],
  "recommendations": [
    "3 displays need scene assignments",
    "2 assigned displays are offline"
  ]
}
```

## Database Schema

### Enhanced DisplayClient Model
```sql
-- The assigned_scene_id field links displays to scenes
CREATE TABLE display_clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT,
    
    -- Scene Assignment
    assigned_scene_id TEXT,  -- FK to scenes.id
    
    -- Status tracking
    is_online BOOLEAN DEFAULT FALSE,
    last_seen DATETIME,
    
    -- Additional fields for enhanced functionality
    current_content_hash TEXT,
    
    -- Indexes for performance
    INDEX idx_assigned_scene (assigned_scene_id),
    INDEX idx_online_status (is_online, last_seen)
);
```

### Query Patterns

#### Count Displays per Scene
```sql
SELECT 
    s.id,
    s.name,
    COUNT(d.id) as display_count,
    SUM(CASE WHEN d.is_online THEN 1 ELSE 0 END) as online_count
FROM scenes s
LEFT JOIN display_clients d ON s.id = d.assigned_scene_id
GROUP BY s.id, s.name;
```

#### Find Unassigned Displays
```sql
SELECT * FROM display_clients 
WHERE assigned_scene_id IS NULL;
```

## Integration Examples

### Frontend Display Management
```javascript
// Get scene with display statistics
const sceneWithDisplays = await fetch('/api/scenes/my-scene/displays');
const data = await sceneWithDisplays.json();

// Show display count in scene list
console.log(`Scene "${data.scene_name}" has ${data.display_stats.total_assigned} displays`);
console.log(`${data.display_stats.online_displays} online, ${data.display_stats.offline_displays} offline`);

// Bulk assign multiple displays to a scene
const bulkAssignment = await fetch('/api/display-scene/assignments/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        displayIds: ['display-1', 'display-2'],
        sceneId: 'emergency-scene',
        overridePrevious: true
    })
});
```

### Management Dashboard Integration
```javascript
// Get dashboard overview
const overview = await fetch('/api/display-scene/dashboard/overview');
const dashboardData = await overview.json();

// Display key metrics
const metrics = dashboardData.summary;
console.log(`Managing ${metrics.total_scenes} scenes across ${metrics.total_assigned_displays} displays`);

// Show recommendations
dashboardData.recommendations.forEach(rec => {
    if (rec) console.log(`⚠️ ${rec}`);
});
```

## Use Cases

### 1. **Emergency Broadcasting**
- Quickly assign all displays to an emergency scene
- Use bulk assignment to override existing assignments
- Monitor assignment success across all locations

### 2. **Location-Based Management**
- Group displays by floor, building, or department
- Assign different scenes to different locations
- Track assignment distribution by location

### 3. **Display Discovery Integration**
- Automatically discovered displays appear in unassigned list
- Easy assignment of newly discovered displays
- Maintain assignments when displays reconnect

### 4. **Scene Performance Monitoring**
- Track which scenes have the most displays
- Monitor online/offline status of assigned displays
- Identify scenes that need attention

## Benefits

### For Administrators
- **Centralized Management**: Single dashboard for all display-scene relationships
- **Bulk Operations**: Efficient management of multiple displays
- **Real-time Status**: Live updates on display connectivity and assignments
- **Location Awareness**: Group and manage displays by physical location

### For System Operations
- **Database Efficiency**: Optimized queries with proper indexing
- **API Consistency**: RESTful endpoints following established patterns
- **Error Handling**: Comprehensive error reporting for failed operations
- **Audit Trail**: Track assignment changes and system state

### For Integration
- **Flexible Schemas**: Pydantic models for type safety and validation
- **Backward Compatibility**: Enhanced endpoints complement existing functionality
- **WebSocket Support**: Real-time updates for assignment changes
- **Documentation**: Comprehensive API documentation and examples

## Next Steps

### Immediate Implementation
1. **Deploy Enhanced Endpoints**: Add the new routes to your API
2. **Update Frontend**: Integrate display statistics in scene management UI
3. **Test Bulk Operations**: Verify bulk assignment functionality

### Future Enhancements
1. **Assignment History**: Track when displays were assigned/unassigned
2. **Override Settings**: Per-display customization of scene parameters
3. **Scheduled Assignments**: Time-based scene assignments
4. **Assignment Templates**: Save and reuse assignment patterns
5. **Advanced Filtering**: Search and filter displays by multiple criteria

This enhanced system provides a robust foundation for managing display-scene relationships at scale while maintaining simplicity for basic use cases.
