# Image Frame Channel - Technical Specification

## Project Overview

### Purpose
A Mimir Platform channel implementation that provides web-based digital photo frame functionality for any display, featuring intelligent image management, slideshow functionality, and seamless integration with the Mimir Platform ecosystem.

### Target Audience
- Mimir Platform users wanting photo frame functionality
- Smart home integrators
- Content creators for digital displays

### Channel Characteristics
- **Channel Type**: Image-generating content channel with self-contained UI
- **Update Schedule**: User-configurable (minutes to days)
- **Schema Version**: 2.1 (supports Web Components and zip distribution)
- **UI Type**: Web Components with optional dashboard slots and full-page routes
- **Content**: Dynamic photo slideshow with intelligent crop management

## Channel Architecture

### Mimir Platform Integration
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Mimir Platform  │    │  PhotoFrame     │    │   ImageScene    │
│ Scene Engine    │◄──►│   Channel       │◄──►│   Renderer      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  SQLite DB +    │
                       │  Image Storage  │
                       └─────────────────┘
```

### Channel Structure
```
channels/photo_frame/
├── config.json              # Channel metadata & configuration (v2.1 schema)
├── channel.py               # Main channel implementation
├── placeholder.jpg          # Default image (first run)
├── current.jpg              # Latest generated/selected image
├── requirements.txt         # Python dependencies
├── ui/                      # Self-contained UI bundle (NEW in v2.1)
│   ├── index.esm.js         # Web Component entry (ESM)
│   ├── manage.esm.js        # Management page component (ESM)
│   ├── styles.css           # Scoped component styles
│   └── assets/              # UI-specific assets (icons, fonts)
├── assets/                  # Server assets (served by API)
│   ├── logo.svg             # Channel branding
│   └── uploads/             # User-uploaded images
├── data/
│   ├── photo_frame.db       # Channel-specific database
│   └── thumbs/              # Generated thumbnails
└── utils/
    ├── image_processor.py   # Image processing utilities
    └── database.py          # Database management
```

## Channel Configuration (config.json)

```json
{
  "schemaVersion": "2.1",
  "id": "com.epaperframe.photoframe",
  "name": "Photo Frame",
  "description": "Digital photo frame with intelligent cropping and slideshow management",
  "version": "1.0.0",
  "author": "Ryan Lane",
  "update_schedule": {
    "unit": "minutes",
    "duration": 15
  },
  "placeholder_image": "placeholder.jpg",
  "current_image": "current.jpg",
  "permissions": ["read:images", "write:images"],
  "ui": [
    {
      "element": "x-photo-frame-card",
      "moduleUrl": "/api/channels/com.epaperframe.photoframe/ui/index.esm.js",
      "styleUrl": "/api/channels/com.epaperframe.photoframe/ui/styles.css",
      "slots": ["dashboard.gallery", "dashboard.sidebar"],
      "propsSchema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
          "user": {"type": "object"},
          "settings": {"type": "object"},
          "stats": {"type": "object"}
        }
      },
      "renderMode": "element",
      "integrity": {
        "module": "sha384-...",
        "style": "sha384-..."
      }
    },
    {
      "route": "/photo-frame",
      "element": "x-photo-frame-manager",
      "moduleUrl": "/api/channels/com.epaperframe.photoframe/ui/manage.esm.js",
      "nav": {
        "label": "Photo Frame",
        "icon": "image"
      },
      "renderMode": "element"
    }
  ],
  "settings": {
    "slideshow_enabled": {
      "type": "boolean",
      "default": true,
      "label": "Enable Slideshow",
      "description": "Automatically rotate through images"
    },
    "order_mode": {
      "type": "select",
      "options": ["added", "random", "custom"],
      "default": "added",
      "label": "Image Order",
      "description": "How to order images in slideshow"
    },
    "crop_mode": {
      "type": "select",
      "options": ["smart_crop", "letterbox", "stretch"],
      "default": "smart_crop",
      "label": "Display Mode",
      "description": "How to fit images to display"
    }
  },
  "assets": [
    {
      "name": "logo",
      "url": "/api/channels/com.epaperframe.photoframe/assets/logo.svg"
    }
  ],
  "capabilities": {
    "supports_orientations": ["landscape", "portrait"],
    "supports_resolutions": ["any"],
    "requires_network": false,
    "storage_type": "local",
    "update_triggers": ["time_based", "manual"]
  }
}
```

## Channel Implementation

### Core Channel Class

```python
# channels/photo_frame/channel.py
import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageOps
import sqlite3
from pathlib import Path

from .utils.image_processor import ImageProcessor
from .utils.database import PhotoFrameDB

class PhotoFrameChannel:
    """
    Photo Frame channel for Mimir Platform
    Provides digital photo frame functionality with intelligent image management
    """
    
    def __init__(self, channel_dir: str):
        self.channel_dir = Path(channel_dir)
        self.config_path = self.channel_dir / "config.json"
        self.config = self._load_config()
        
        # Initialize components
        self.db = PhotoFrameDB(self.channel_dir / "data" / "photo_frame.db")
        self.image_processor = ImageProcessor(
            upload_dir=self.channel_dir / "static" / "uploads",
            thumb_dir=self.channel_dir / "data" / "thumbs"
        )
        
        # State tracking
        self.last_update = None
        self.last_error = None
        self.current_image_id = None
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load channel configuration"""
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def _ensure_directories(self):
        """Create necessary directories"""
        dirs = [
            self.channel_dir / "static" / "uploads",
            self.channel_dir / "data" / "thumbs",
            self.channel_dir / "data"
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def id(self) -> str:
        """Channel identifier"""
        return "photo_frame"
    
    async def render_image(
        self, 
        resolution: Tuple[int, int], 
        orientation: str, 
        settings: Dict[str, Any]
    ) -> str:
        """
        Generate/select next image for display
        
        Args:
            resolution: (width, height) in pixels
            orientation: "landscape" or "portrait"
            settings: User configuration from Mimir Platform
            
        Returns:
            Relative path to image file
        """
        try:
            # Get next image based on slideshow settings
            image_record = await self._get_next_image(settings)
            
            if not image_record:
                # No images available, return placeholder
                return self.config["placeholder_image"]
            
            # Process image for display
            output_path = await self._process_image_for_display(
                image_record, resolution, orientation, settings
            )
            
            # Update statistics
            await self._update_image_stats(image_record["id"])
            
            self.current_image_id = image_record["id"]
            self.last_update = datetime.now(timezone.utc)
            self.last_error = None
            
            return self.config["current_image"]
            
        except Exception as e:
            self.last_error = str(e)
            # Return last successful image or placeholder
            return await self._get_fallback_image()
    
    async def _get_next_image(self, settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select next image based on slideshow settings"""
        if not settings.get("slideshow_enabled", True):
            # If slideshow disabled, return current image
            if self.current_image_id:
                return self.db.get_image(self.current_image_id)
            
        order_mode = settings.get("order_mode", "added")
        enabled_images = self.db.get_enabled_images()
        
        if not enabled_images:
            return None
        
        if order_mode == "random":
            import random
            return random.choice(enabled_images)
        elif order_mode == "custom":
            # Sort by custom sort_order, then by least recently shown
            return self._get_next_by_custom_order(enabled_images)
        else:  # "added"
            # Sort by creation date, prefer never shown
            return self._get_next_by_date_added(enabled_images)
    
    async def _process_image_for_display(
        self, 
        image_record: Dict[str, Any], 
        resolution: Tuple[int, int], 
        orientation: str,
        settings: Dict[str, Any]
    ) -> str:
        """Process image according to crop settings and display mode"""
        
        source_path = self.channel_dir / "static" / "uploads" / image_record["filename"]
        output_path = self.channel_dir / self.config["current_image"]
        
        crop_mode = settings.get("crop_mode", "smart_crop")
        
        if crop_mode == "smart_crop":
            # Use stored crop coordinates
            await self.image_processor.render_with_crop(
                source_path=source_path,
                output_path=output_path,
                resolution=resolution,
                crop_x=image_record.get("crop_x", 0),
                crop_y=image_record.get("crop_y", 0),
                crop_width=image_record.get("crop_width", 100),
                crop_height=image_record.get("crop_height", 100)
            )
        elif crop_mode == "letterbox":
            # Preserve aspect ratio with borders
            await self.image_processor.render_letterbox(
                source_path=source_path,
                output_path=output_path,
                resolution=resolution
            )
        else:  # "stretch"
            # Stretch to fill (may distort)
            await self.image_processor.render_stretch(
                source_path=source_path,
                output_path=output_path,
                resolution=resolution
            )
        
        return str(output_path)
    
    async def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, str]:
        """Validate channel settings"""
        errors = {}
        
        # Validate order_mode
        valid_orders = ["added", "random", "custom"]
        if settings.get("order_mode") not in valid_orders:
            errors["order_mode"] = f"Must be one of: {', '.join(valid_orders)}"
        
        # Validate crop_mode
        valid_crops = ["smart_crop", "letterbox", "stretch"]
        if settings.get("crop_mode") not in valid_crops:
            errors["crop_mode"] = f"Must be one of: {', '.join(valid_crops)}"
        
        return errors
    
    def get_status(self) -> Dict[str, Any]:
        """Get channel status for debugging"""
        image_count = self.db.get_image_count()
        enabled_count = self.db.get_enabled_image_count()
        
        return {
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "last_error": self.last_error,
            "current_image_id": self.current_image_id,
            "total_images": image_count,
            "enabled_images": enabled_count,
            "database_ok": self.db.check_health(),
            "storage_usage": self._get_storage_usage()
        }
    
    def _get_storage_usage(self) -> Dict[str, Any]:
        """Calculate storage usage"""
        uploads_dir = self.channel_dir / "static" / "uploads"
        thumbs_dir = self.channel_dir / "data" / "thumbs"
        
        def dir_size(path):
            if not path.exists():
                return 0
            return sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        
        return {
            "uploads_mb": round(dir_size(uploads_dir) / 1024 / 1024, 2),
            "thumbs_mb": round(dir_size(thumbs_dir) / 1024 / 1024, 2),
            "total_mb": round((dir_size(uploads_dir) + dir_size(thumbs_dir)) / 1024 / 1024, 2)
        }
```

## Database Schema

### Images Table
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    original_name TEXT NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    times_shown INTEGER DEFAULT 0,
    last_shown_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Crop settings (percentage-based)
    crop_x REAL DEFAULT 0.0,
    crop_y REAL DEFAULT 0.0,
    crop_width REAL DEFAULT 100.0,
    crop_height REAL DEFAULT 100.0,
    
    -- Display preferences
    preserve_aspect_ratio BOOLEAN DEFAULT FALSE
);
```

### Settings Table
```sql
CREATE TABLE channel_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

The channel provides REST API endpoints accessible under the Mimir API path:

```
/api/channels/com.epaperframe.photoframe/
```

### Required Core Endpoints

- `GET /api/channels/com.epaperframe.photoframe/image` - Returns current display image
- `GET /api/channels/com.epaperframe.photoframe/status` - Returns channel status and basic info
- `POST /api/channels/com.epaperframe.photoframe/update` - Triggers manual update

### Management API (for Web Components)

- `GET /api/channels/com.epaperframe.photoframe/images` - List all uploaded images with metadata
- `POST /api/channels/com.epaperframe.photoframe/upload` - Upload new image
- `DELETE /api/channels/com.epaperframe.photoframe/images/{id}` - Delete specific image
- `PUT /api/channels/com.epaperframe.photoframe/images/{id}` - Update image metadata
- `GET /api/channels/com.epaperframe.photoframe/settings` - Get current settings
- `PUT /api/channels/com.epaperframe.photoframe/settings` - Update settings
- `GET /api/channels/com.epaperframe.photoframe/hardware` - Get Inky display hardware info

### UI Assets

- `GET /api/channels/com.epaperframe.photoframe/ui/index.esm.js` - Main dashboard component
- `GET /api/channels/com.epaperframe.photoframe/ui/manage.esm.js` - Management interface component
- `GET /api/channels/com.epaperframe.photoframe/ui/styles.css` - Component styles
- `GET /api/channels/com.epaperframe.photoframe/assets/*` - Static assets (logos, etc.)

## Web Management Interface

### API Routes Implementation

```python
# Channel-specific API routes for Web Components
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse

@app.get("/api/channels/com.epaperframe.photoframe/images")
async def list_images():
    """List all uploaded images with metadata"""
    images = channel.db.get_all_images()
    return JSONResponse(images)

@app.post("/api/channels/com.epaperframe.photoframe/upload")
async def upload_images(files: List[UploadFile] = File(...)):
    """Handle image uploads"""
    results = []
    
    for file in files:
        try:
            # Process upload
            image_data = await channel.image_processor.save_upload(file)
            
            # Add to database
            image_id = channel.db.add_image(image_data)
            
            results.append({
                "filename": file.filename,
                "success": True,
                "image_id": image_id
            })
            
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    return JSONResponse({"results": results})

@app.post("/channels/photo_frame/images/{image_id}/update")
async def update_image(
    image_id: int,
    title: str = Form(""),
    description: str = Form(""),
    crop_x: float = Form(0),
    crop_y: float = Form(0),
    crop_width: float = Form(100),
    crop_height: float = Form(100),
    preserve_aspect_ratio: bool = Form(False)
):
    """Update image metadata and crop settings"""
    
    success = channel.db.update_image(image_id, {
        "title": title,
        "description": description,
        "crop_x": crop_x,
        "crop_y": crop_y,
        "crop_width": crop_width,
        "crop_height": crop_height,
        "preserve_aspect_ratio": preserve_aspect_ratio
    })
    
    if success:
        return JSONResponse({"success": True})
    else:
        return JSONResponse({"success": False, "error": "Image not found"}, status_code=404)

@app.post("/channels/photo_frame/images/{image_id}/toggle")
async def toggle_image(image_id: int):
    """Enable/disable image in slideshow"""
    success = channel.db.toggle_image_enabled(image_id)
    
    if success:
        image = channel.db.get_image(image_id)
        return JSONResponse({"success": True, "enabled": image["enabled"]})
    else:
        return JSONResponse({"success": False, "error": "Image not found"}, status_code=404)

@app.delete("/channels/photo_frame/images/{image_id}")
async def delete_image(image_id: int):
    """Delete image from collection"""
    success = await channel.delete_image(image_id)
    
    if success:
        return JSONResponse({"success": True})
    else:
        return JSONResponse({"success": False, "error": "Image not found"}, status_code=404)
```

## Frontend Components

### Management Interface (templates/manage.html)

```html
<!DOCTYPE html>
<html>
<head>
    <title>Photo Frame Channel - Management</title>
    <link rel="stylesheet" href="/channels/photo_frame/static/css/photo_frame.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Photo Frame Management</h1>
            <div class="status-bar">
                <span class="status-item">Images: {{ status.total_images }}</span>
                <span class="status-item">Enabled: {{ status.enabled_images }}</span>
                <span class="status-item">Storage: {{ status.storage_usage.total_mb }}MB</span>
            </div>
        </header>
        
        <nav class="action-bar">
            <a href="/channels/photo_frame/upload" class="btn btn-primary">Upload Images</a>
            <button onclick="testChannel()" class="btn btn-secondary">Test Display</button>
        </nav>
        
        <main class="image-grid">
            {% for image in images %}
                {% include "partials/image_card.html" %}
            {% endfor %}
        </main>
    </div>
    
    <script src="/channels/photo_frame/static/js/photo_frame.js"></script>
</body>
</html>
```

### Image Card Component (templates/partials/image_card.html)

```html
<div class="image-card" data-image-id="{{ image.id }}">
    <div class="image-preview">
        <img src="/channels/photo_frame/data/thumbs/{{ image.filename }}" 
             alt="{{ image.title or image.original_name }}">
        <div class="image-overlay">
            <button onclick="editImage({{ image.id }})" class="btn-icon" title="Edit">✏️</button>
            <button onclick="toggleImage({{ image.id }})" class="btn-icon" title="Toggle">
                {{ "🚫" if not image.enabled else "▶️" }}
            </button>
            <button onclick="deleteImage({{ image.id }})" class="btn-icon" title="Delete">🗑️</button>
        </div>
    </div>
    
    <div class="image-info">
        <h3>{{ image.title or image.original_name }}</h3>
        <p>{{ image.description }}</p>
        <div class="image-stats">
            <span>{{ image.width }}×{{ image.height }}</span>
            <span>Shown: {{ image.times_shown }} times</span>
        </div>
    </div>
    
    <!-- Crop Editor (hidden by default) -->
    <div class="crop-editor" id="crop-editor-{{ image.id }}" style="display: none;">
        {% include "partials/crop_editor.html" %}
    </div>
</div>
```

## Integration with Mimir Platform

### Channel Registration and Lifecycle

The channel integrates with Mimir's v2.1 platform through:

1. **Discovery**: Mimir scans `channels/` directory and finds `config.json` with schema v2.1
2. **Registration**: Channel instance created with Web Component support
3. **UI Loading**: Web Components loaded as ESM modules with integrity checking
4. **API Routing**: Channel APIs exposed under `/api/channels/{id}/` namespace
5. **Asset Serving**: Static assets and UI components served with proper CORS headers

### Web Component Integration

```javascript
// Mimir Platform loads components like this:
const module = await import('/api/channels/com.epaperframe.photoframe/ui/index.esm.js');

// Dashboard integration
const dashboardSlot = document.querySelector('slot[name="dashboard.gallery"]');
const photoCard = document.createElement('x-photo-frame-card');
photoCard.setAttribute('user', JSON.stringify(currentUser));
photoCard.setAttribute('settings', JSON.stringify(channelSettings));
dashboardSlot.appendChild(photoCard);

// Navigation integration
window.addEventListener('mimir:route-change', (e) => {
    if (e.detail.route === '/photo-frame') {
        const manager = document.createElement('x-photo-frame-manager');
        document.querySelector('main').appendChild(manager);
    }
});
```

### Platform API Integration

```python
# Mimir Platform integration hooks
class MimirPhotoFrameChannel(PhotoFrameChannel):
    """Extended channel class for Mimir Platform integration"""
    
    def __init__(self, channel_dir: str, mimir_api):
        super().__init__(channel_dir)
        self.mimir = mimir_api
        
    async def on_display_update(self, display_info):
        """Called when display configuration changes"""
        # Update our settings to match display capabilities
        if hasattr(display_info, 'resolution'):
            await self.update_settings({
                'target_width': display_info.resolution[0],
                'target_height': display_info.resolution[1]
            })
    
    async def on_platform_event(self, event_type: str, data: dict):
        """Handle platform-wide events"""
        if event_type == 'user_login':
            # Potentially sync user-specific settings
            pass
        elif event_type == 'system_sleep':
            # Pause any background operations
            self.pause_slideshow()
        elif event_type == 'system_wake':
            # Resume operations
            self.resume_slideshow()
    
    def get_dashboard_props(self, user_context: dict) -> dict:
        """Return props for dashboard component"""
        return {
            'user': user_context,
            'settings': self.get_settings(),
            'stats': {
                'image_count': len(self.db.get_all_images()),
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'current_image': self.current_image_id
            }
        }
```
5. **Settings**: User settings managed through Mimir's configuration system

### Update Flow

```python
# In Mimir Scene Engine
async def update_photo_frame_channel():
    # Get user settings from scene configuration
    settings = scene.get_channel_settings("photo_frame")
    
    # Get display properties
    resolution = scene.get_display_resolution()
    orientation = scene.get_display_orientation()
    
    # Request new image from channel
    image_path = await photo_frame_channel.render_image(
        resolution, orientation, settings
    )
    
    # Update scene with new image
    scene.update_channel_content("photo_frame", image_path)
```

## Performance Considerations

### Image Processing Optimization
- **Lazy Thumbnail Generation**: Thumbnails created on-demand
- **Cached Renders**: Output images cached until source changes
- **Async Processing**: Non-blocking image operations
- **Memory Management**: Large images processed in chunks

### Database Optimization
- **Indexed Queries**: Primary keys and frequently queried fields indexed
- **Connection Pooling**: Reuse database connections
- **Batch Operations**: Multiple updates in single transaction
- **Cleanup Tasks**: Periodic cleanup of orphaned files

### Storage Management
- **File Naming**: Hash-based unique filenames prevent conflicts
- **Directory Structure**: Organized storage for efficient access
- **Cleanup Utilities**: Tools for removing unused files
- **Size Limits**: Configurable limits on upload sizes

## Error Handling & Recovery

### Error Categories
1. **Image Processing Errors**: Corrupt files, unsupported formats
2. **Database Errors**: Connection failures, constraint violations
3. **Storage Errors**: Disk full, permission issues
4. **Network Errors**: Upload timeouts, connection issues

### Fallback Strategy
```python
async def _get_fallback_image(self) -> str:
    """Get fallback image when primary rendering fails"""
    
    # Try last successful image
    if self.current_image_id and os.path.exists(self.config["current_image"]):
        return self.config["current_image"]
    
    # Try any enabled image
    images = self.db.get_enabled_images()
    if images:
        return await self._render_simple_fallback(images[0])
    
    # Use placeholder
    return self.config["placeholder_image"]
```

## Security Considerations

### File Security
- **Upload Validation**: File type and size restrictions
- **Filename Sanitization**: Hash-based safe filenames
- **Directory Isolation**: Channel files isolated from system
- **Permission Control**: Restricted file system access

### Input Validation
- **Image Metadata**: EXIF data sanitization
- **Crop Coordinates**: Range validation (0-100%)
- **Settings Validation**: Type checking and bounds validation
- **SQL Injection Prevention**: Parameterized queries only

## Development & Testing

### Development Mode
- **Mocked Hardware**: Simulated display for testing
- **Test Data**: Sample images for development
- **Debug Logging**: Detailed logging for troubleshooting
- **Status Dashboard**: Development status monitoring

### Testing Strategy
- **Unit Tests**: Individual component testing
- **Integration Tests**: Channel-platform integration
- **Performance Tests**: Load testing with many images
- **UI Tests**: Web interface functionality

This technical specification provides a comprehensive guide for implementing the Image Frame as a Mimir Platform channel, following their architectural guidelines while preserving the core functionality and user experience of the original application.
