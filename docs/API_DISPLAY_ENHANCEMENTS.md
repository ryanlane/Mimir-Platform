# Enhanced Display Client API Support

## Overview

This document outlines the API enhancements required to support the new display client capabilities including:

- **Hostname tracking** - Automatic hardware identification
- **mDNS discovery** - Network-based display discovery
- **Webhook manual updates** - Immediate update triggers
- **Redis distribution** - Multi-display content distribution

## 🔧 Database Changes

### New Fields Added to `display_clients` Table

```sql
-- Hostname tracking
ALTER TABLE display_clients ADD COLUMN hostname VARCHAR(255);

-- Webhook capabilities
ALTER TABLE display_clients ADD COLUMN webhook_port INTEGER;

-- Redis distribution support
ALTER TABLE display_clients ADD COLUMN redis_distribution BOOLEAN DEFAULT FALSE;
ALTER TABLE display_clients ADD COLUMN content_claiming BOOLEAN DEFAULT FALSE;
```

## 📡 Enhanced Registration Endpoint

### Updated Registration Schema

The `POST /api/displays/register` endpoint now accepts additional fields:

```json
{
  "name": "Kitchen Display",
  "description": "Main kitchen display",
  "location": "Kitchen Counter",
  "hostname": "colorframe05",
  "capabilities": {
    "resolution": [800, 480],
    "supported_formats": ["jpg", "png"],
    "orientation": "landscape",
    "refresh_rate_hz": 1,
    "redis_distribution": true,
    "content_claiming": true
  },
  "tags": ["kitchen", "inky"],
  "client_version": "2.0.0",
  "webhook_port": 8080
}
```

### Enhanced Response

The registration response now includes:

```json
{
  "id": "display-uuid",
  "name": "Kitchen Display",
  "hostname": "colorframe05",
  "webhook_port": 8080,
  "webhook_url": "http://colorframe05:8080",
  "redis_distribution": true,
  "content_claiming": true,
  // ... other existing fields
}
```

## 🚀 New API Endpoints

### 1. Manual Update Triggers

#### `POST /api/displays/{display_id}/update`
Trigger immediate content update on a display.

**Request:**
```json
{
  "reason": "Content updated via admin panel"
}
```

**Response:**
```json
{
  "message": "Update triggered on display Kitchen Display",
  "display_id": "display-uuid",
  "webhook_response": {"status": "update_triggered"}
}
```

#### `POST /api/displays/{display_id}/refresh`
Force complete refresh (bypassing cache) on a display.

**Request:**
```json
{
  "reason": "Emergency content refresh"
}
```

**Response:**
```json
{
  "message": "Refresh triggered on display Kitchen Display",
  "display_id": "display-uuid", 
  "webhook_response": {"status": "refresh_triggered"}
}
```

### 2. Webhook Status Check

#### `GET /api/displays/{display_id}/webhook_status`
Check if a display's webhook server is accessible.

**Response:**
```json
{
  "webhook_available": true,
  "webhook_url": "http://colorframe05:8080/status",
  "display_status": {
    "display_id": "display-uuid",
    "hostname": "colorframe05",
    "last_update": "2025-08-26T15:30:00Z",
    "current_assignment": true
  },
  "last_checked": "2025-08-26T15:35:00Z"
}
```

### 3. mDNS Network Discovery

#### `GET /api/displays/discover`
Discover displays on the network via mDNS.

**Parameters:**
- `timeout` (optional): Discovery timeout in seconds (default: 5)

**Response:**
```json
{
  "discovered_displays": [
    {
      "service_name": "mimir-display-uuid._mimir-display._tcp.local.",
      "hostname": "colorframe05",
      "display_name": "Kitchen Display",
      "display_id": "display-uuid",
      "location": "Kitchen Counter",
      "resolution": "800x480",
      "client_version": "2.0.0",
      "webhook_port": 8080,
      "webhook_url": "http://192.168.1.105:8080",
      "addresses": ["192.168.1.105"],
      "port": 5353,
      "discovered_at": "2025-08-26T15:30:00Z"
    }
  ],
  "discovery_timeout": 5,
  "total_found": 1,
  "discovery_completed_at": "2025-08-26T15:30:05Z"
}
```

## 🔄 WebSocket Events

### Enhanced Event Broadcasting

The API now broadcasts additional events:

#### `display_manual_update`
Sent when manual update is triggered via API.

```json
{
  "event": "display_manual_update",
  "data": {
    "displayId": "display-uuid",
    "displayName": "Kitchen Display",
    "action": "update", // or "refresh"
    "reason": "Content updated via admin panel",
    "webhook_url": "http://colorframe05:8080/update",
    "triggeredBy": {
      "source": "api",
      "timestamp": "2025-08-26T15:30:00Z"
    }
  }
}
```

#### `display_client_registered` (Enhanced)
Now includes additional fields:

```json
{
  "event": "display_client_registered",
  "data": {
    "displayId": "display-uuid",
    "name": "Kitchen Display",
    "location": "Kitchen Counter",
    "hostname": "colorframe05",
    "webhook_url": "http://colorframe05:8080",
    "capabilities": {
      "redis_distribution": true,
      "content_claiming": true,
      // ... other capabilities
    }
  }
}
```

## 🛠 Frontend Integration

### Display Management UI Enhancements

The frontend should now support:

1. **Display Discovery**: Button to scan for displays on network
2. **Manual Update Controls**: Update/refresh buttons for each display
3. **Webhook Status Indicators**: Show which displays are reachable
4. **Enhanced Display Cards**: Show hostname, webhook URL, and capabilities

### Example Frontend Integration

```javascript
// Discover displays on network
const discoverDisplays = async () => {
  const response = await api.get('/api/displays/discover?timeout=10');
  return response.data.discovered_displays;
};

// Trigger manual update
const triggerUpdate = async (displayId, reason) => {
  const response = await api.post(`/api/displays/${displayId}/update`, {
    reason: reason
  });
  return response.data;
};

// Check webhook status
const checkWebhookStatus = async (displayId) => {
  const response = await api.get(`/api/displays/${displayId}/webhook_status`);
  return response.data;
};
```

## 🧪 Testing

### Test the Enhanced API

```bash
# Test registration with new fields
curl -X POST http://localhost:5000/api/displays/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Display",
    "hostname": "testframe01",
    "webhook_port": 8080,
    "capabilities": {
      "resolution": [800, 480],
      "redis_distribution": true
    }
  }'

# Test manual update
curl -X POST http://localhost:5000/api/displays/{display_id}/update \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test update"}'

# Test discovery
curl http://localhost:5000/api/displays/discover?timeout=5
```

## 📋 Implementation Checklist

- ✅ Updated Pydantic models for registration
- ✅ Enhanced database schema with new fields
- ✅ Added manual update endpoints
- ✅ Added webhook status checking
- ✅ Added mDNS discovery endpoint
- ✅ Updated requirements.txt with dependencies
- ✅ Created database migration script
- ✅ Enhanced WebSocket event broadcasting
- 🔄 **Pending**: Database migration execution
- 🔄 **Pending**: Frontend UI updates
- 🔄 **Pending**: End-to-end testing

## 🚨 Dependencies

Make sure to install the new dependencies:

```bash
pip install httpx>=0.25.0 zeroconf>=0.56.0
```

## 🔧 Configuration

Add to your API server configuration:

```env
# Enable enhanced display features
ENABLE_MDNS_DISCOVERY=true
WEBHOOK_TIMEOUT=5
MAX_DISCOVERY_TIMEOUT=30
```

This completes the API enhancements needed to support all the new display client capabilities!
