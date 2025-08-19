# Mimir Platform - New Channel Architecture

**Version:** 2.0  
**Date:** August 18, 2025  
**Status:** Architecture Specification  

---

## Overview

This document defines the new sandboxed, configuration-driven channel architecture for the Mimir Platform. This architecture replaces the previous complex Python plugin system with a simpler, more secure, and user-friendly approach.

---

## Core Principles

1. **Configuration-Driven Discovery** - Channels discovered via `config.json` files
2. **Platform-Managed Scheduling** - Scene engine handles update timing
3. **On-Demand Generation** - Channels generate images when requested
4. **Sandboxed Execution** - Each channel is isolated in its own directory
5. **Simple Installation** - Drop folder into `channels/` directory

---

## Channel Structure

### Directory Layout

```
channels/
└── weather_channel/
    ├── config.json          # Channel metadata & configuration
    ├── channel.py           # Main channel implementation
    ├── placeholder.jpg      # Default image (first run)
    ├── current.jpg          # Latest generated image
    ├── requirements.txt     # Python dependencies (optional)
    ├── static/              # Static assets (optional)
    └── templates/           # Custom UI templates (optional)
```

### Required Files

- **`config.json`** - Channel metadata and configuration schema
- **`channel.py`** - Python module implementing the Channel protocol
- **`placeholder.jpg`** - Default image shown on first run or errors

### Optional Files

- **`requirements.txt`** - Python dependencies for the channel
- **`static/`** - Static files for custom management UI
- **`templates/`** - HTML templates for complex settings UI

---

## Configuration Schema (config.json)

### Basic Structure

```json
{
  "name": "Weather Display",
  "description": "Shows current weather conditions with forecast",
  "version": "1.0.0",
  "author": "Channel Developer",
  "update_schedule": {
    "unit": "minutes",
    "duration": 15
  },
  "placeholder_image": "placeholder.jpg",
  "current_image": "current.jpg",
  "settings_type": "simple",
  "settings": {
    "api_key": {
      "type": "string",
      "required": true,
      "secret": true,
      "label": "API Key",
      "description": "Your weather service API key"
    },
    "location": {
      "type": "string",
      "required": true,
      "default": "New York",
      "label": "Location",
      "description": "City name for weather data"
    },
    "units": {
      "type": "select",
      "options": ["metric", "imperial"],
      "default": "metric",
      "label": "Temperature Units"
    }
  }
}
```

### Configuration Fields

#### Required Fields

- **`name`** (string) - Human-readable channel name
- **`description`** (string) - Brief description of channel functionality
- **`update_schedule`** (object) - When to refresh content
  - **`unit`** - One of: "seconds", "minutes", "hours", "days"
  - **`duration`** (number) - How many units between updates
- **`placeholder_image`** (string) - Filename of default image
- **`current_image`** (string) - Filename where generated image is saved

#### Optional Fields

- **`version`** (string) - Channel version (semantic versioning)
- **`author`** (string) - Channel author/maintainer
- **`settings_type`** (string) - "simple" or "complex" (default: "simple")
- **`settings`** (object) - Configuration schema for simple settings
- **`management_url`** (string) - Custom management UI path (complex only)

### Update Schedule Units

- **`seconds`** - For testing or very dynamic content (1-59)
- **`minutes`** - For frequently updated content (1-60)
- **`hours`** - For moderately dynamic content (1-24)
- **`days`** - For daily content updates (1-7)

### Settings Types

#### Simple Settings (`"settings_type": "simple"`)

Platform generates UI automatically based on `settings` schema:

```json
{
  "settings_type": "simple",
  "settings": {
    "text_field": {
      "type": "string",
      "required": true,
      "default": "Default Value",
      "label": "Display Label",
      "description": "Help text for users"
    },
    "number_field": {
      "type": "number",
      "min": 0,
      "max": 100,
      "default": 50
    },
    "boolean_field": {
      "type": "boolean",
      "default": false
    },
    "select_field": {
      "type": "select",
      "options": ["option1", "option2", "option3"],
      "default": "option1"
    },
    "secret_field": {
      "type": "string",
      "secret": true,
      "label": "API Key"
    }
  }
}
```

#### Complex Settings (`"settings_type": "complex"`)

Channel provides custom web UI for advanced configuration:

```json
{
  "settings_type": "complex",
  "management_url": "/channels/my_channel/manage"
}
```

---

## Channel Python Interface

### Protocol Definition

```python
from typing import Protocol, Tuple, Dict, Any

class Channel(Protocol):
    """
    Channel interface for Mimir Platform v2.0
    Channels generate images on-demand when requested by scenes
    """
    
    @property
    def id(self) -> str:
        """Unique channel identifier (matches directory name)"""
        pass
    
    @property
    def config(self) -> Dict[str, Any]:
        """Loaded configuration from config.json"""
        pass
    
    async def render_image(
        self, 
        resolution: Tuple[int, int], 
        orientation: str, 
        settings: Dict[str, Any]
    ) -> str:
        """
        Generate image for given resolution and orientation.
        
        Args:
            resolution: (width, height) in pixels
            orientation: "landscape" or "portrait"  
            settings: User-configured settings from config.json
            
        Returns:
            Relative path to generated image file (e.g., "current.jpg")
            
        Raises:
            ChannelError: If image generation fails
        """
        pass
    
    async def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate user settings.
        
        Args:
            settings: User-provided configuration values
            
        Returns:
            Dictionary of field_name -> error_message for invalid fields
            Empty dict if all settings are valid
        """
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current channel status for debugging.
        
        Returns:
            Status information including last update time, errors, etc.
        """
        pass
```

### Implementation Example

```python
# channels/weather_channel/channel.py
import os
import json
import asyncio
from datetime import datetime
from typing import Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont
import requests

class WeatherChannel:
    def __init__(self, channel_dir: str):
        self.channel_dir = channel_dir
        self.config_path = os.path.join(channel_dir, "config.json")
        self.config = self._load_config()
        self.last_update = None
        self.last_error = None
    
    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    @property
    def id(self) -> str:
        return os.path.basename(self.channel_dir)
    
    async def render_image(
        self, 
        resolution: Tuple[int, int], 
        orientation: str, 
        settings: Dict[str, Any]
    ) -> str:
        """Generate weather display image"""
        try:
            # Fetch weather data
            weather_data = await self._fetch_weather(settings)
            
            # Generate image
            image_path = await self._create_weather_image(
                weather_data, resolution, orientation
            )
            
            self.last_update = datetime.now()
            self.last_error = None
            
            return self.config["current_image"]
            
        except Exception as e:
            self.last_error = str(e)
            # Return placeholder on error
            return self.config["placeholder_image"]
    
    async def _fetch_weather(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch weather data from API"""
        api_key = settings.get("api_key")
        location = settings.get("location", "New York")
        units = settings.get("units", "metric")
        
        if not api_key:
            raise ValueError("API key required")
        
        # Make API request (example)
        url = f"https://api.weather.com/v1/current?key={api_key}&q={location}&units={units}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        return response.json()
    
    async def _create_weather_image(
        self, 
        weather_data: Dict[str, Any], 
        resolution: Tuple[int, int], 
        orientation: str
    ) -> str:
        """Create weather display image"""
        width, height = resolution
        
        # Create image
        image = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(image)
        
        # Add weather information
        # (Implementation details...)
        
        # Save image
        output_path = os.path.join(self.channel_dir, self.config["current_image"])
        image.save(output_path, 'JPEG', quality=90)
        
        return output_path
    
    async def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, str]:
        """Validate user settings"""
        errors = {}
        
        if not settings.get("api_key"):
            errors["api_key"] = "API key is required"
        
        if not settings.get("location"):
            errors["location"] = "Location is required"
        
        return errors
    
    def get_status(self) -> Dict[str, Any]:
        """Get channel status"""
        return {
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "last_error": self.last_error,
            "config_valid": os.path.exists(self.config_path),
            "placeholder_exists": os.path.exists(
                os.path.join(self.channel_dir, self.config["placeholder_image"])
            )
        }
```

---

## Platform Integration

### Channel Discovery

The platform scans the `channels/` directory on startup:

```python
# core/channel_discovery.py
import os
import json
import importlib.util
from typing import Dict, List, Any

class ChannelDiscovery:
    def __init__(self, channels_dir: str = "channels"):
        self.channels_dir = channels_dir
        self.channels = {}
    
    def discover_channels(self) -> Dict[str, Any]:
        """Discover all channels in channels directory"""
        channels = {}
        
        for item in os.listdir(self.channels_dir):
            channel_path = os.path.join(self.channels_dir, item)
            
            if not os.path.isdir(channel_path):
                continue
            
            config_path = os.path.join(channel_path, "config.json")
            if not os.path.exists(config_path):
                continue
            
            try:
                # Load configuration
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Load Python module
                channel_module = self._load_channel_module(channel_path)
                
                # Create channel instance
                channel_class = getattr(channel_module, f"{item.title()}Channel")
                channel = channel_class(channel_path)
                
                channels[item] = {
                    "config": config,
                    "instance": channel,
                    "path": channel_path
                }
                
            except Exception as e:
                print(f"Failed to load channel {item}: {e}")
        
        return channels
    
    def _load_channel_module(self, channel_path: str):
        """Dynamically load channel Python module"""
        module_path = os.path.join(channel_path, "channel.py")
        spec = importlib.util.spec_from_file_location("channel", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
```

### Scene Engine Integration

The scene engine schedules channel updates based on configuration:

```python
# core/scene_engine.py (updated)
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

class SceneEngine:
    def __init__(self):
        self.channels = {}
        self.active_scene = None
        self.update_tasks = {}
    
    def register_channel(self, channel_id: str, channel_data: Dict[str, Any]):
        """Register discovered channel"""
        self.channels[channel_id] = channel_data
        
        # Start update scheduler for this channel
        self._schedule_channel_updates(channel_id)
    
    def _schedule_channel_updates(self, channel_id: str):
        """Schedule automatic updates for channel"""
        channel_data = self.channels[channel_id]
        config = channel_data["config"]
        
        update_schedule = config["update_schedule"]
        interval = self._calculate_interval(update_schedule)
        
        async def update_loop():
            while True:
                try:
                    await self._update_channel(channel_id)
                    await asyncio.sleep(interval)
                except Exception as e:
                    print(f"Channel {channel_id} update failed: {e}")
                    await asyncio.sleep(60)  # Retry in 1 minute on error
        
        # Cancel existing task if any
        if channel_id in self.update_tasks:
            self.update_tasks[channel_id].cancel()
        
        # Start new update task
        self.update_tasks[channel_id] = asyncio.create_task(update_loop())
    
    async def _update_channel(self, channel_id: str):
        """Update channel image if it's used in active scene"""
        if not self.active_scene:
            return
        
        # Check if channel is used in active scene
        scene_channels = self.active_scene.get("channels", [])
        if channel_id not in scene_channels:
            return
        
        # Get display resolution and orientation
        resolution = (800, 600)  # From display settings
        orientation = "landscape"  # From display settings
        
        # Get user settings for this channel
        settings = self._get_channel_settings(channel_id)
        
        # Request new image from channel
        channel_data = self.channels[channel_id]
        channel_instance = channel_data["instance"]
        
        image_path = await channel_instance.render_image(
            resolution, orientation, settings
        )
        
        # Update scene engine state
        self._update_channel_state(channel_id, image_path)
    
    def _calculate_interval(self, update_schedule: Dict[str, Any]) -> int:
        """Convert update schedule to seconds"""
        unit = update_schedule["unit"]
        duration = update_schedule["duration"]
        
        multipliers = {
            "seconds": 1,
            "minutes": 60,
            "hours": 3600,
            "days": 86400
        }
        
        return duration * multipliers.get(unit, 60)
```

---

## API Endpoints

### Channel Management

```python
# New API endpoints for channel management

@app.get("/api/channels")
async def list_channels():
    """List all discovered channels"""
    channels = []
    for channel_id, channel_data in scene_engine.channels.items():
        config = channel_data["config"]
        channels.append({
            "id": channel_id,
            "name": config["name"],
            "description": config["description"],
            "version": config.get("version", "1.0.0"),
            "settings_type": config.get("settings_type", "simple"),
            "management_url": config.get("management_url"),
            "status": channel_data["instance"].get_status()
        })
    return {"channels": channels}

@app.get("/api/channels/{channel_id}/config")
async def get_channel_config(channel_id: str):
    """Get channel configuration schema"""
    if channel_id not in scene_engine.channels:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return scene_engine.channels[channel_id]["config"]

@app.get("/api/channels/{channel_id}/settings")
async def get_channel_settings(channel_id: str):
    """Get current user settings for channel"""
    # Load from scene configuration or defaults
    settings = scene_engine.get_channel_settings(channel_id)
    return {"settings": settings}

@app.post("/api/channels/{channel_id}/settings")
async def update_channel_settings(channel_id: str, settings: Dict[str, Any]):
    """Update channel settings"""
    if channel_id not in scene_engine.channels:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel = scene_engine.channels[channel_id]["instance"]
    
    # Validate settings
    errors = await channel.validate_settings(settings)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    
    # Save settings
    scene_engine.update_channel_settings(channel_id, settings)
    
    return {"message": "Settings updated successfully"}

@app.post("/api/channels/{channel_id}/test")
async def test_channel(channel_id: str):
    """Test channel by generating a sample image"""
    if channel_id not in scene_engine.channels:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    try:
        channel = scene_engine.channels[channel_id]["instance"]
        settings = scene_engine.get_channel_settings(channel_id)
        
        image_path = await channel.render_image(
            (400, 300), "landscape", settings
        )
        
        return {
            "success": True,
            "image_path": f"/channels/{channel_id}/{image_path}",
            "message": "Test image generated successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Test failed"
        }
```

---

## Error Handling & Fallbacks

### Error States

1. **Channel Discovery Errors**
   - Missing `config.json` → Skip channel, log warning
   - Invalid JSON → Skip channel, show error in console
   - Missing `channel.py` → Skip channel, show error in console

2. **Runtime Errors**
   - Image generation fails → Use cached last successful image
   - Network timeout → Use cached image, schedule retry
   - Invalid settings → Show validation errors in UI

3. **Fallback Strategy**
   ```
   1. Try to generate new image
   2. If fails, use last successful cached image
   3. If no cache, use placeholder.jpg
   4. If no placeholder, show error state in scene
   ```

### Console Error Display

```json
{
  "channel_id": "weather_channel",
  "status": "error",
  "last_error": "API key invalid",
  "last_successful_update": "2025-08-18T10:30:00Z",
  "using_fallback": true,
  "fallback_type": "cached_image"
}
```

---

## Installation & Distribution

### Channel Installation

1. **Download/Create** channel folder
2. **Drop into** `channels/` directory
3. **Restart** Mimir Platform (or hot-reload if supported)
4. **Configure** settings in console UI

### Channel Distribution

- **GitHub repositories** with standardized structure
- **Zip files** for manual installation
- **Future:** Package manager integration

### Example Installation

```bash
# Clone a channel repository
git clone https://github.com/user/mimir-weather-channel.git

# Move to channels directory
mv mimir-weather-channel channels/weather

# Install dependencies (if requirements.txt exists)
pip install -r channels/weather/requirements.txt

# Restart Mimir Platform
systemctl restart mimir
```

---

## Migration from Current Architecture

### Phase 1: Add Discovery System
1. Implement `ChannelDiscovery` class
2. Update scene engine to use discovered channels
3. Keep existing ImageFrameChannel working alongside

### Phase 2: Convert Existing Channels
1. Convert ImageFrameChannel to new format
2. Test thoroughly with existing scenes
3. Update documentation

### Phase 3: Remove Legacy Code
1. Remove old channel registration code
2. Clean up unused interfaces
3. Update all documentation

---

This new architecture provides a clean, scalable foundation for channel development while maintaining simplicity for users and developers.
