# Photo Frame Channel - Frontend Integration Guide

## Overview

This document outlines the requirements for integrating the **Photo Frame Channel** (`com.epaperframe.photoframe`) into the Mimir Platform v2.4 web frontend. The channel provides digital photo frame functionality with intelligent image management, enhanced settings, and security compliance.

## 🔌 Platform Requirements

### Schema Version Support
- **Platform Version**: Mimir v2.4
- **Schema Version**: `2.4`
- **Channel ID**: `com.epaperframe.photoframe`

### Security Requirements (Critical)
The platform **MUST** enforce Subresource Integrity (SRI) validation for all channel resources:

```json
{
  "integrity": {
    "module": "sha384-e1c5i8U5teEKEFKJIG1KZ/r/cOpRIIk3CyXEdtM4eFesPbzJNdX9A8HhgLU3aMRD",
    "style": "sha384-WDQcixiu+7CxVwxbEb5MdHQjhF7uWwiKCYVLUTgkCwMGmBwThlpklpNsVspPIims"
  }
}
```

## 🛠️ API Endpoints

The platform needs to proxy the following endpoints to the channel backend:

| Method | Endpoint | Purpose | Request Body |
|--------|----------|---------|--------------|
| `GET` | `/api/channels/com.epaperframe.photoframe/images` | List all images | None |
| `POST` | `/api/channels/com.epaperframe.photoframe/upload` | Upload new images | `multipart/form-data` |
| `PUT` | `/api/channels/com.epaperframe.photoframe/images/{id}` | Update image metadata | JSON |
| `POST` | `/api/channels/com.epaperframe.photoframe/images/{id}/toggle` | Enable/disable image | None |
| `DELETE` | `/api/channels/com.epaperframe.photoframe/images/{id}` | Delete image | None |
| `GET` | `/api/channels/com.epaperframe.photoframe/settings` | Get channel settings | None |
| `PUT` | `/api/channels/com.epaperframe.photoframe/settings` | Update settings | JSON |
| `GET` | `/api/channels/com.epaperframe.photoframe/hardware` | Get hardware status | None |

### Authentication
All requests must include authentication credentials:
```javascript
fetch(endpoint, {
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json'
  }
})
```

## ⚙️ Enhanced Settings Schema

The platform must support these enhanced settings with validation:

### New Settings Fields

#### `slideshow_interval`
- **Type**: `integer`
- **Range**: 5-300 seconds
- **Default**: 30
- **Title**: "Slideshow Speed (seconds)"
- **Description**: "Time between image changes in slideshow mode"

#### `transition_effect`
- **Type**: `string`
- **Enum**: `["fade", "slide", "none"]`
- **Default**: "fade"
- **Title**: "Transition Effect"
- **Description**: "Visual transition between images"

### Complete Settings Schema
```json
{
  "slideshow_enabled": {
    "type": "boolean",
    "title": "Enable Slideshow",
    "description": "Automatically rotate through images"
  },
  "order_mode": {
    "type": "string",
    "enum": ["added", "random", "custom"],
    "title": "Image Order",
    "description": "How to order images in slideshow"
  },
  "crop_mode": {
    "type": "string",
    "enum": ["smart_crop", "letterbox", "stretch"],
    "title": "Display Mode",
    "description": "How to fit images to display"
  },
  "slideshow_interval": {
    "type": "integer",
    "minimum": 5,
    "maximum": 300,
    "title": "Slideshow Speed (seconds)",
    "description": "Time between image changes in slideshow mode",
    "default": 30
  },
  "transition_effect": {
    "type": "string",
    "enum": ["fade", "slide", "none"],
    "title": "Transition Effect",
    "description": "Visual transition between images",
    "default": "fade"
  }
}
```

### Settings Validation
The platform should support **partial settings updates**:

```javascript
// ✅ Valid partial update
POST /api/channels/com.epaperframe.photoframe/settings
{
  "slideshow_interval": 60  // Only updating one field
}

// ✅ Valid multiple updates  
PUT /api/channels/com.epaperframe.photoframe/settings
{
  "slideshow_interval": 120,
  "transition_effect": "fade"
}

// ❌ Should reject invalid values and return validation errors
{
  "slideshow_interval": 500,      // > 300 max
  "transition_effect": "invalid"  // Not in enum
}
```

## 🎨 UI Component Integration

### Dashboard Widget (`x-photo-frame-card`)

**Component Details:**
- **Element**: `x-photo-frame-card`
- **Module URL**: `/api/channels/com.epaperframe.photoframe/ui/index.esm.js`
- **Style URL**: `/api/channels/com.epaperframe.photoframe/ui/styles.css`
- **Slots**: `["dashboard.gallery", "dashboard.sidebar"]`
- **Render Mode**: `element`

**Props Schema:**
```javascript
{
  "user": { "type": "object" },
  "settings": { "type": "object" },
  "stats": { "type": "object" }
}
```

**Implementation:**
```html
<x-photo-frame-card 
  data-hostprops='{"user": {...}, "settings": {...}, "stats": {...}}'
></x-photo-frame-card>
```

### Management Interface (`x-photo-frame-manager`)

**Component Details:**
- **Element**: `x-photo-frame-manager`
- **Module URL**: `/api/channels/com.epaperframe.photoframe/ui/manage.esm.js`
- **Route**: `/photo-frame`
- **Navigation**: 
  - **Label**: "Photo Frame"
  - **Icon**: "image"
- **Render Mode**: `element`

**Implementation:**
The platform should load this component when the user navigates to `/photo-frame` and include it in the navigation menu.

## 🔄 Dynamic Update Schedule

The platform must support **settings-driven update scheduling**:

```json
{
  "update_schedule": {
    "unit": "minutes",
    "duration": 15,
    "settings_driven": true,
    "settings_key": "slideshow_interval"
  }
}
```

**Implementation Logic:**
1. When `slideshow_interval` setting changes, update the channel's refresh schedule
2. Convert seconds to minutes: `Math.max(0.083, slideshow_interval / 60)`
3. Minimum effective interval: 5 seconds (0.083 minutes)
4. Platform should re-schedule the channel's update cycle accordingly

## 🖼️ File Upload Handling

### Upload Endpoint Requirements
```javascript
// Multiple file upload support
const formData = new FormData();
files.forEach(file => formData.append('files', file));

const response = await fetch('/api/channels/com.epaperframe.photoframe/upload', {
  method: 'POST',
  body: formData,
  credentials: 'include'
});
```

### Expected Response Format
```json
{
  "results": [
    {
      "filename": "image.jpg",
      "success": true,
      "image_id": 7
    }
  ]
}
```

### Supported File Types
- **JPEG** (`.jpg`, `.jpeg`)
- **PNG** (`.png`)
- **GIF** (`.gif`)

## 🚨 Error Handling

### API Error Responses
The platform should handle these error scenarios:

```javascript
// Validation errors
{
  "detail": "Validation failed",
  "errors": {
    "slideshow_interval": "Must be between 5 and 300 seconds",
    "transition_effect": "Must be one of: fade, slide, none"
  }
}

// Upload errors
{
  "detail": "Upload failed",
  "errors": ["File too large", "Unsupported format"]
}
```

### Graceful Degradation
- If channel endpoints are unavailable, show appropriate error messages
- Maintain UI functionality where possible
- Cache settings locally when offline

## 🔐 Security Considerations

### Content Security Policy
Ensure CSP allows:
```
script-src 'self' 'sha384-e1c5i8U5teEKEFKJIG1KZ/r/cOpRIIk3CyXEdtM4eFesPbzJNdX9A8HhgLU3aMRD';
style-src 'self' 'sha384-WDQcixiu+7CxVwxbEb5MdHQjhF7uWwiKCYVLUTgkCwMGmBwThlpklpNsVspPIims';
```

### CORS Configuration
```javascript
// Allow credentials for authentication
credentials: 'include'

// Handle preflight requests for PUT/DELETE methods
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
```

## 🧪 Testing Requirements

### Endpoints to Test
1. **Channel Registration**: Verify channel appears as `com.epaperframe.photoframe`
2. **Settings API**: 
   - GET returns current settings
   - PUT accepts partial updates
   - Validates ranges and enums
3. **Image API**: 
   - GET returns image list
   - POST upload works with multipart data
   - PUT/DELETE operations succeed
4. **File Serving**: Static assets load correctly with integrity validation

### Test Data
```javascript
// Valid settings test
{
  "slideshow_interval": 60,
  "transition_effect": "fade"
}

// Invalid settings test (should fail)
{
  "slideshow_interval": 1000,
  "transition_effect": "invalid"
}
```

## 📦 Deployment Checklist

- [ ] Platform supports Mimir v2.4 schema
- [ ] SRI integrity validation implemented
- [ ] All API endpoints proxied correctly
- [ ] Web Components load with proper props
- [ ] Settings validation working
- [ ] File upload functionality tested
- [ ] Navigation menu includes Photo Frame
- [ ] Update scheduling implemented
- [ ] Error handling graceful
- [ ] Security headers configured

## 🚀 Live Testing

The channel has been tested against the live API service:
- **Endpoint**: `oak:5000`
- **Status**: ✅ All endpoints functional
- **Images**: 7 test images loaded
- **Settings**: Enhanced settings validated
- **Upload**: File upload working correctly

## 📞 Support

For technical questions or issues during integration:
- **Repository**: `ryanlane/image-frame-channel-mimir`
- **Branch**: `main`
- **Last Updated**: August 22, 2025

---

**Note**: This channel implements enhanced security with integrity hashes and new slideshow settings. Ensure all integrity values match exactly for proper loading.
