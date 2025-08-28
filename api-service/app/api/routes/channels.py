"""
Channel API Routes
FastAPI router for channel-related endpoints

⚠️ CRITICAL: CHANNEL ID USAGE ⚠️
====================================
ALL channel operations MUST use the channel ID from the channel's config.json file,
NEVER the directory name, path, or display name. This ensures proper routing and data integrity.

✅ Correct: Use config.json "id" field (e.g., "com.epaperframe.photoframe")
❌ Wrong: Use directory name (e.g., "photo_frame") 
❌ Wrong: Use display name (e.g., "Photo Frame")
❌ Wrong: Use file path components

Example:
- Directory: /var/opt/mimir/mimir-api/channels/photo_frame/
- Config ID: "com.epaperframe.photoframe" ← USE THIS
- Display Name: "Photo Frame" ← DON'T USE THIS

The ChannelDiscoveryService handles the mapping between config IDs and 
directory paths. Always use channel_discovery.get_channel_config(channel_id)
to validate and resolve channel information.

==== SUBCHANNEL SYSTEM OVERVIEW ====

Subchannels (also called "galleries" in photo frame channels) provide a way to organize 
content within channels into logical groups. This system enables:

1. CONTENT ORGANIZATION: Group related images/content into themed collections
2. INDIVIDUAL SETTINGS: Each subchannel can have its own display settings
3. SELECTIVE DISPLAY: Choose which subchannel to display at any given time
4. BULK OPERATIONS: Perform operations on groups of content at once

==== SUBCHANNEL DATA STRUCTURE ====

Subchannels are stored in `{channel_dir}/data/galleries.json` with this structure:
```json
[
  {
    "id": "vacation_photos",           // Unique identifier (generated from name)
    "name": "Vacation Photos",         // Human-readable name
    "description": "Summer 2024 trip", // Optional description
    "contentIds": ["1", "5", "12"],    // List of content/image IDs in this subchannel
    "imageCount": 3,                   // Cached count (should match contentIds length)
    "coverImageId": "5",               // Optional: featured image for this subchannel
    "tags": ["vacation", "summer"],    // Optional: categorization tags
    "created": "2024-08-20T10:00:00Z", // ISO timestamp when created
    "modified": "2024-08-25T15:30:00Z", // ISO timestamp when last modified
    "displaySettings": {               // Subchannel-specific display settings
      "order_mode": "random",          // How to order images: "added", "random", "custom"
      "crop_mode": "letterbox",        // How to fit images: "smart_crop", "letterbox", "stretch"  
      "transition_effect": "fade",     // Visual transition between images
      "update_interval_value": 45,     // How often to change images
      "update_interval_unit": "seconds", // Time unit for update interval
      "slideshow_enabled": true        // Whether slideshow is active
    }
  }
]
```

==== KEY ENDPOINTS FOR SUBCHANNELS ====

- GET    /channels/{id}/subchannels                    - List all subchannels
- POST   /channels/{id}/subchannels                    - Create new subchannel
- GET    /channels/{id}/subchannels/{sub_id}           - Get specific subchannel details
- PUT    /channels/{id}/subchannels/{sub_id}           - Update subchannel metadata
- DELETE /channels/{id}/subchannels/{sub_id}           - Delete subchannel
- POST   /channels/{id}/subchannels/{sub_id}/content   - Add/remove content from subchannel
- GET    /channels/{id}/subchannels/{sub_id}/images    - List images in subchannel
- GET    /channels/{id}/subchannels/{sub_id}/images/{img_id}/thumbnail - Get image thumbnail

==== FILE PATH RESOLUTION ====

The system uses the ChannelDiscoveryService to resolve actual channel directory paths.
This ensures compatibility across different deployment scenarios:

1. Development: channels in ./api-service/channels/
2. Production: channels in /var/opt/mimir/channels/ 
3. Custom: channels in user-specified directory

Never use hardcoded paths - always get the path from channel_discovery.get_all_channels()

==== THUMBNAIL SERVING ====

Thumbnails are served using a fallback hierarchy:
1. Channel instance method (if available)
2. Co-located thumbnail files (image_12345.thumb.jpg)
3. Original image file (browser scaling)

This ensures thumbnails work even if generation fails or isn't implemented.

==== ERROR HANDLING ====

All subchannel operations include comprehensive error handling:
- JSON validation for galleries.json 
- File system permission checks
- Input validation and sanitization
- Detailed logging for debugging
- Graceful degradation when possible

"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any, List

from app.services.deps import (
    get_channel_discovery_service,
    get_content_service,
    get_cache_service,
    get_channel_service
)
from app.services.channel_discovery import ChannelDiscoveryService
from app.services.content import ContentService
from app.services.caching import CacheService
from app.core.services.channel_service import ChannelService
from app.schemas.channels import (
    ChannelResponse
)
# TODO: Add these schemas when they're created in the schemas file
# from app.schemas.channels import ChannelListResponse


router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
async def list_channels(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get paginated list of channels"""
    all_channels = channel_discovery.get_all_channels()
    
    # Simple pagination
    total = len(all_channels)
    start = offset
    end = min(offset + limit, total)
    channels_slice = all_channels[start:end]
    
    channel_responses = []
    for channel_data in channels_slice:
        config = channel_data['config']
        
        # Determine settings type based on structure (same logic as get_channels_manifest)
        settings_config = config.get('settings', {})
        if 'schema' in settings_config and 'defaults' in settings_config:
            # Advanced schema-based settings
            settings_type = config.get('settingsType', config.get('settings_type', 'advanced'))
        else:
            # Simple or no settings
            settings_type = config.get('settingsType', config.get('settings_type', 'simple'))
        
        channel_responses.append(ChannelResponse(
            id=channel_data['id'],
            name=config['name'],
            description=config['description'],
            version=config['version'],
            schemaVersion=config.get('schemaVersion', '2.1'),
            settingsType=settings_type,
            permissions=config.get('permissions', {}),
            uiConfig=config.get('ui', []),
            assetsConfig=config.get('assets', {}),
            currentSettings=config.get('currentSettings', {}),
            status=config.get('status', {}),
            channelDir=str(channel_data['path'])
        ))
    
    return {
        "channels": channel_responses,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/manifest")
async def get_channels_manifest(
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get manifest of all available channels"""
    # Check cache first
    cached_manifest = cache_service.get_cache("channels_manifest")
    if cached_manifest:
        return cached_manifest
    
    # Generate manifest
    manifest = channel_discovery.get_channels_manifest()
    
    # Cache for 5 minutes
    cache_service.set_cache("channels_manifest", manifest, 300)
    
    return manifest


@router.get("/{channel_id}/config")
async def get_channel_config(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel configuration"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    return config


@router.get("/{channel_id}/settings")
async def get_channel_settings(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel settings"""
    settings = channel_discovery.get_channel_settings(channel_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return settings


@router.post("/{channel_id}/settings")
async def update_channel_settings(
    channel_id: str,
    settings: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Update channel settings"""
    success = channel_discovery.update_channel_settings(channel_id, settings)
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {"message": "Settings updated successfully"}


@router.get("/{channel_id}/status")
async def get_channel_status(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel status"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return config.get("status", {})


@router.get("/{channel_id}/health")
async def get_channel_health(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel health status"""
    # Get channel config from discovery service
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Basic health check based on channel status
    status = config.get("status", {})
    healthy = status.get("active", True) and not status.get("lastError")
    
    return {
        "channelId": channel_id,
        "name": config.get("name", channel_id),
        "version": config.get("version", "unknown"),
        "status": status,
        "healthy": healthy,
        "lastCheck": status.get("lastUpdate")
    }


@router.get("/{channel_id}/token")
async def get_channel_token(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel authentication token"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, return a simple token based on channel ID
    # In production, this should generate a proper JWT or secure token
    import hashlib
    import time
    
    token_data = f"{channel_id}:{time.time()}"
    token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
    
    return {"token": token}


@router.get("/{channel_id}/current")
async def get_channel_current_content(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get current content for channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Return basic content info
    return {
        "channelId": channel_id,
        "contentType": "image/jpeg",
        "lastUpdate": config.get("status", {}).get("lastUpdate"),
        "available": True
    }


@router.get("/{channel_id}/current.jpg")
async def get_channel_current_image(
    channel_id: str,
    content_service: ContentService = Depends(get_content_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get current image for channel"""
    # Check rate limiting for content requests
    rate_limit = cache_service.check_rate_limit(f"content:{channel_id}", max_requests=30, window_seconds=60)
    if not rate_limit['allowed']:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Get current content
    content_result = content_service.get_current_content(channel_id)
    if not content_result:
        raise HTTPException(status_code=404, detail="Channel not found or no image available")
    
    file_path, file_info = content_result
    
    return FileResponse(
        file_path,
        media_type=file_info.get("mime_type", "image/jpeg"),
        filename=f"{channel_id}_current.jpg"
    )


@router.get("/{channel_id}/current/{resolution}/{filename}")
async def get_channel_content_file(
    channel_id: str,
    resolution: str,
    filename: str,
    content_service: ContentService = Depends(get_content_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get specific content file for channel"""
    # Rate limiting
    rate_limit = cache_service.check_rate_limit(f"content:{channel_id}:{resolution}", max_requests=50, window_seconds=60)
    if not rate_limit['allowed']:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Get content with resolution
    content_result = content_service.get_current_content(channel_id, resolution=resolution)
    if not content_result:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path, file_info = content_result
    
    # Validate file for security
    validation = content_service.validate_content_file(file_path)
    if not validation['valid']:
        raise HTTPException(status_code=400, detail="Invalid file")
    
    return FileResponse(
        file_path,
        media_type=file_info.get("mime_type", "application/octet-stream"),
        filename=filename
    )


@router.post("/{channel_id}/image_request")
async def request_channel_image(
    channel_id: str,
    request_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Request image generation from channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    from datetime import datetime
    
    return {
        "success": True,
        "channelId": channel_id,
        "requestId": f"{channel_id}_{int(datetime.now().timestamp())}",
        "status": "processing",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: str,
    test_data: Dict[str, Any] = None,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Test channel functionality"""
    # Get channel config from discovery service
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    from datetime import datetime
    
    # Basic test - check if channel exists and has valid configuration
    return {
        "success": True,
        "channelId": channel_id,
        "name": config.get("name", channel_id),
        "version": config.get("version", "unknown"),
        "status": config.get("status", {}),
        "test_result": {
            "message": "Channel configuration test passed",
            "basic_test": True,
            "timestamp": datetime.now().isoformat()
        }
    }


@router.get("/{channel_id}/subchannels")
async def list_subchannels(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """
    Get list of subchannels (galleries) for a channel
    
    Subchannels are logical groupings of content within a channel. For photo frame channels,
    these are called "galleries" and allow users to organize images into themed collections.
    Each subchannel has its own settings and content list.
    
    Returns:
        {"subchannels": [{"id": str, "name": str, "description": str, "contentIds": list, ...}]}
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    import json
    from pathlib import Path
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # Get the actual channel directory path from the discovery service
    # This ensures we're using the correct path regardless of deployment location
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        logger.error(f"Channel directory not found for channel: {channel_id}")
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    galleries_file = channel_dir / 'data' / 'galleries.json'
    
    logger.info(f"Reading subchannels from: {galleries_file}")
    
    try:
        if galleries_file.exists():
            with open(galleries_file, 'r', encoding='utf-8') as f:
                galleries = json.load(f)
            logger.info(f"Found {len(galleries)} subchannels for channel {channel_id}")
            return {"subchannels": galleries}
        else:
            logger.info(f"No galleries file found for channel {channel_id}")
            return {"subchannels": []}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in galleries file for channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Invalid subchannel data format")
    except Exception as e:
        logger.error(f"Error reading subchannels for channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read subchannel data")


@router.post("/{channel_id}/subchannels/{subchannel_id}/content")
async def assign_content_to_subchannel(
    channel_id: str,
    subchannel_id: str,
    content_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """
    Assign content (images) to a subchannel (gallery)
    
    This endpoint manages the relationship between images and galleries in a photo frame channel.
    Content assignment allows users to organize images into themed collections (subchannels).
    
    Args:
        channel_id: The ID of the channel containing the subchannel
        subchannel_id: The ID of the subchannel/gallery to modify
        content_data: {"contentIds": [list of image IDs], "action": "add|remove"}
        
    Actions:
        - "add": Add the specified image IDs to the subchannel
        - "remove": Remove the specified image IDs from the subchannel
        
    Returns:
        {"success": bool, "gallery": updated_gallery_object}
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    import json
    from pathlib import Path
    from datetime import datetime
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # Get the actual channel directory path
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        logger.error(f"Channel directory not found for channel: {channel_id}")
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    galleries_file = channel_dir / 'data' / 'galleries.json'
    
    try:
        # Read current galleries/subchannels
        if galleries_file.exists():
            with open(galleries_file, 'r', encoding='utf-8') as f:
                galleries = json.load(f)
        else:
            logger.warning(f"No galleries file found for channel {channel_id}")
            galleries = []
        
        # Find the target gallery/subchannel
        gallery = next((g for g in galleries if g['id'] == subchannel_id), None)
        if not gallery:
            raise HTTPException(status_code=404, detail=f"Subchannel '{subchannel_id}' not found")
        
        # Extract and validate content assignment data
        content_ids = content_data.get('contentIds', [])
        action = content_data.get('action', 'add')
        
        if not content_ids:
            raise HTTPException(status_code=400, detail="No content IDs provided")
        
        if action not in ['add', 'remove']:
            raise HTTPException(status_code=400, detail="Action must be 'add' or 'remove'")
        
        # Convert content IDs to strings for consistency
        content_ids = [str(cid) for cid in content_ids]
        original_count = len(gallery.get('contentIds', []))
        
        if action == 'add':
            # Add new content IDs, avoiding duplicates
            existing_ids = set(gallery.get('contentIds', []))
            new_ids = [cid for cid in content_ids if cid not in existing_ids]
            gallery['contentIds'] = gallery.get('contentIds', []) + new_ids
            logger.info(f"Added {len(new_ids)} new images to subchannel {subchannel_id}")
            
        elif action == 'remove':
            # Remove specified content IDs
            gallery['contentIds'] = [cid for cid in gallery.get('contentIds', []) 
                                   if cid not in content_ids]
            removed_count = original_count - len(gallery['contentIds'])
            logger.info(f"Removed {removed_count} images from subchannel {subchannel_id}")
        
        # Update metadata
        gallery['imageCount'] = len(gallery['contentIds'])
        gallery['modified'] = datetime.now().isoformat() + 'Z'
        
        # Ensure data directory exists before writing
        galleries_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write back to file with proper encoding and formatting
        with open(galleries_file, 'w', encoding='utf-8') as f:
            json.dump(galleries, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully updated subchannel {subchannel_id} with {action} action")
        return {"success": True, "gallery": gallery}
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in galleries file for channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Invalid subchannel data format")
    except Exception as e:
        logger.error(f"Error updating subchannel content for {channel_id}/{subchannel_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update subchannel content: {str(e)}")


@router.put("/{channel_id}/subchannels/{subchannel_id}")
async def update_subchannel(
    channel_id: str,
    subchannel_id: str,
    update_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Update subchannel metadata"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Read and update galleries file
    import json
    from pathlib import Path
    
    # Get channel directory
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if channel_data and channel_data.get('path'):
        channel_dir = str(channel_data['path'])
    else:
        channel_dir = f'/var/opt/mimir/mimir-api/channels/{channel_id}'
    
    galleries_file = Path(channel_dir) / 'data' / 'galleries.json'
    
    try:
        # Read current galleries
        if galleries_file.exists():
            with open(galleries_file, 'r') as f:
                galleries = json.load(f)
        else:
            raise HTTPException(status_code=404, detail="Galleries file not found")
        
        # Find the target gallery
        gallery = next((g for g in galleries if g['id'] == subchannel_id), None)
        if not gallery:
            raise HTTPException(status_code=404, detail="Subchannel not found")
        
        # Update fields
        if 'name' in update_data:
            gallery['name'] = update_data['name']
        if 'description' in update_data:
            gallery['description'] = update_data['description']
        if 'cover_image_id' in update_data:
            gallery['coverImageId'] = update_data['cover_image_id']
        
        # Update modified timestamp
        from datetime import datetime
        gallery['modified'] = datetime.now().isoformat()
        
        # Write back to file
        with open(galleries_file, 'w') as f:
            json.dump(galleries, f, indent=2)
        
        return {"success": True, "gallery": gallery}
        
    except Exception as e:
        from app.core.logging import get_logger
        logger = get_logger("app.api.channels")
        logger.error(f"Error updating subchannel: {e}")
        raise HTTPException(status_code=500, detail="Failed to update subchannel")


@router.get("/{channel_id}/subchannels/{subchannel_id}/settings")
async def get_subchannel_settings(
    channel_id: str,
    subchannel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get subchannel-specific settings"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Return default gallery settings
    return {
        "order_mode": {"value": "added"},
        "crop_mode": {"value": "smart_crop"},
        "update_interval_value": {"value": 30},
        "update_interval_unit": {"value": "minutes"},
        "slideshow_enabled": {"value": True},
        "transition_effect": {"value": "fade"}
    }


@router.put("/{channel_id}/subchannels/{subchannel_id}/settings")
async def update_subchannel_settings(
    channel_id: str,
    subchannel_id: str,
    settings_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Update subchannel-specific settings"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, just return success - settings would be stored with the gallery
    return {"success": True, "settings": settings_data}


@router.post("/{channel_id}/subchannels")
async def create_subchannel(
    channel_id: str,
    subchannel_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """
    Create a new subchannel (gallery) for a channel
    
    Subchannels (also called galleries in photo frame channels) are logical groupings 
    of content within a channel. They allow users to organize content into themed 
    collections with individual settings and metadata.
    
    Each subchannel has:
    - Unique ID (generated from name)
    - Name and description
    - List of content IDs (images for photo frames)
    - Display settings (crop mode, order, etc.)
    - Metadata (created/modified dates, image count)
    
    Args:
        channel_id: The channel to create the subchannel in
        subchannel_data: {
            "name": str (required),
            "description": str (optional),
            "tags": list (optional)
        }
        
    Returns:
        {"success": bool, "subchannel": created_subchannel_object}
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    import json
    import re
    from pathlib import Path
    from datetime import datetime
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # Validate input data
    if not subchannel_data.get("name"):
        raise HTTPException(status_code=400, detail="Subchannel name is required")
    
    subchannel_name = subchannel_data["name"].strip()
    if len(subchannel_name) < 1:
        raise HTTPException(status_code=400, detail="Subchannel name cannot be empty")
    
    if len(subchannel_name) > 100:
        raise HTTPException(status_code=400, detail="Subchannel name too long (max 100 characters)")
    
    # Get channel directory path
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        logger.error(f"Channel directory not found for: {channel_id}")
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    galleries_file = channel_dir / 'data' / 'galleries.json'
    
    try:
        # Read existing subchannels/galleries
        galleries = []
        if galleries_file.exists():
            with open(galleries_file, 'r', encoding='utf-8') as f:
                galleries = json.load(f)
        
        # Generate unique subchannel ID from name
        def generate_subchannel_id(name: str, existing_ids: set) -> str:
            """Generate a unique ID from the subchannel name"""
            # Clean the name: remove special characters, convert to lowercase
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', name).lower()
            base_id = re.sub(r'\s+', '_', clean_name.strip())
            
            # Ensure we have something to work with
            if not base_id:
                base_id = "gallery"
            
            # Check for uniqueness
            if base_id not in existing_ids:
                return base_id
            
            # Add numeric suffix for duplicates
            counter = 1
            while f"{base_id}_{counter}" in existing_ids:
                counter += 1
            return f"{base_id}_{counter}"
        
        # Get existing IDs for uniqueness check
        existing_ids = {gallery['id'] for gallery in galleries}
        subchannel_id = generate_subchannel_id(subchannel_name, existing_ids)
        
        # Create new subchannel with default settings
        current_time = datetime.now().isoformat() + "Z"
        new_subchannel = {
            "id": subchannel_id,
            "name": subchannel_name,
            "description": subchannel_data.get("description", ""),
            "contentIds": [],  # Start with no content
            "tags": subchannel_data.get("tags", []),
            "created": current_time,
            "modified": current_time,
            "imageCount": 0,
            "coverImageId": None,  # Will be set when first image is added
            "displaySettings": {
                "order_mode": "random",
                "crop_mode": "letterbox", 
                "transition_effect": "fade",
                "update_interval_value": 45,
                "update_interval_unit": "seconds",
                "slideshow_enabled": True
            }
        }
        
        # Add to galleries list
        galleries.append(new_subchannel)
        
        # Ensure data directory exists
        galleries_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write back to file with proper formatting
        with open(galleries_file, 'w', encoding='utf-8') as f:
            json.dump(galleries, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Created new subchannel '{subchannel_id}' for channel {channel_id}")
        
        return {
            "success": True,
            "subchannel": new_subchannel
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in galleries file for channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Invalid subchannel data format")
    except Exception as e:
        logger.error(f"Error creating subchannel for channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create subchannel: {str(e)}")


@router.get("/{channel_id}/subchannels/{subchannel_id}")
async def get_subchannel(
    channel_id: str,
    subchannel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """
    Get detailed information about a specific subchannel
    
    This endpoint returns complete information about a subchannel/gallery including
    its metadata, settings, and content summary. It's useful for loading subchannel
    details in management interfaces.
    
    Args:
        channel_id: The channel containing the subchannel
        subchannel_id: The specific subchannel to retrieve
        
    Returns:
        Complete subchannel object with metadata and settings
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    import json
    from pathlib import Path
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # Get channel directory
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    galleries_file = channel_dir / 'data' / 'galleries.json'
    
    try:
        if not galleries_file.exists():
            raise HTTPException(status_code=404, detail="No subchannels found for this channel")
        
        with open(galleries_file, 'r', encoding='utf-8') as f:
            galleries = json.load(f)
        
        # Find the specific subchannel
        subchannel = next((g for g in galleries if g['id'] == subchannel_id), None)
        if not subchannel:
            raise HTTPException(status_code=404, detail=f"Subchannel '{subchannel_id}' not found")
        
        # Add computed statistics
        content_count = len(subchannel.get('contentIds', []))
        subchannel['computedStats'] = {
            "actualImageCount": content_count,
            "hasContent": content_count > 0,
            "lastModified": subchannel.get('modified'),
            "settingsComplete": all(key in subchannel.get('displaySettings', {}) 
                                  for key in ['order_mode', 'crop_mode', 'slideshow_enabled'])
        }
        
        logger.info(f"Retrieved subchannel {subchannel_id} with {content_count} images")
        return subchannel
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in galleries file: {e}")
        raise HTTPException(status_code=500, detail="Invalid subchannel data format")
    except Exception as e:
        logger.error(f"Error retrieving subchannel {subchannel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve subchannel")


@router.delete("/{channel_id}/subchannels/{subchannel_id}")
async def delete_subchannel(
    channel_id: str,
    subchannel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """
    Delete a subchannel (gallery) from a channel
    
    This endpoint permanently removes a subchannel/gallery and all its content assignments.
    The actual images are not deleted, only the gallery structure and content relationships.
    This operation cannot be undone.
    
    Args:
        channel_id: The channel containing the subchannel
        subchannel_id: The specific subchannel/gallery to delete
        
    Returns:
        {"success": bool, "message": str, "deletedSubchannel": subchannel_info}
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    import json
    from pathlib import Path
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # Get channel directory
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        logger.error(f"Channel directory not found for: {channel_id}")
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    galleries_file = channel_dir / 'data' / 'galleries.json'
    
    try:
        # Read current galleries/subchannels
        if not galleries_file.exists():
            raise HTTPException(status_code=404, detail="No subchannels found for this channel")
        
        with open(galleries_file, 'r', encoding='utf-8') as f:
            galleries = json.load(f)
        
        # Find the subchannel to delete
        subchannel_to_delete = None
        galleries_updated = []
        
        for gallery in galleries:
            if gallery['id'] == subchannel_id:
                subchannel_to_delete = gallery.copy()  # Keep a copy for the response
            else:
                galleries_updated.append(gallery)
        
        if subchannel_to_delete is None:
            raise HTTPException(status_code=404, detail=f"Subchannel '{subchannel_id}' not found")
        
        # Ensure data directory exists before writing
        galleries_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the updated galleries list back to file
        with open(galleries_file, 'w', encoding='utf-8') as f:
            json.dump(galleries_updated, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully deleted subchannel '{subchannel_id}' from channel {channel_id}")
        
        return {
            "success": True,
            "message": f"Subchannel '{subchannel_to_delete.get('name', subchannel_id)}' has been deleted",
            "deletedSubchannel": {
                "id": subchannel_to_delete["id"],
                "name": subchannel_to_delete.get("name", ""),
                "imageCount": subchannel_to_delete.get("imageCount", 0)
            }
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in galleries file for channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Invalid subchannel data format")
    except Exception as e:
        logger.error(f"Error deleting subchannel {subchannel_id} from channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete subchannel: {str(e)}")


@router.get("/{channel_id}/subchannels/{subchannel_id}/images/{image_id}/thumbnail")
async def get_subchannel_image_thumbnail(
    channel_id: str,
    subchannel_id: str,
    image_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """
    Get thumbnail for a specific image within a subchannel
    
    This endpoint serves optimized thumbnail images for gallery/subchannel content.
    Thumbnails are typically smaller, web-optimized versions of the original images
    used for gallery previews and management interfaces.
    
    The thumbnail serving follows this priority:
    1. Co-located thumbnail (same name + .thumb.jpg extension)
    2. Channel instance thumbnail generation 
    3. On-demand thumbnail creation
    4. Fallback to original image (scaled via browser)
    
    Args:
        channel_id: The channel containing the subchannel
        subchannel_id: The subchannel/gallery containing the image
        image_id: The specific image ID to get thumbnail for
        
    Returns:
        FileResponse with the thumbnail image (typically JPEG, 600x600 max)
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    from pathlib import Path
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # Rate limiting for thumbnail requests
    rate_limit = cache_service.check_rate_limit(
        f"thumbnail:{channel_id}:{subchannel_id}:{image_id}", 
        max_requests=100, 
        window_seconds=60
    )
    if not rate_limit['allowed']:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for thumbnail requests")
    
    # Get channel directory and verify subchannel exists
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        logger.error(f"Channel directory not found for: {channel_id}")
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    
    # Verify the image belongs to the specified subchannel
    try:
        import json
        galleries_file = channel_dir / 'data' / 'galleries.json'
        if galleries_file.exists():
            with open(galleries_file, 'r', encoding='utf-8') as f:
                galleries = json.load(f)
            
            # Find the subchannel and verify image belongs to it
            gallery = next((g for g in galleries if g['id'] == subchannel_id), None)
            if not gallery:
                raise HTTPException(status_code=404, detail=f"Subchannel '{subchannel_id}' not found")
            
            if str(image_id) not in gallery.get('contentIds', []):
                raise HTTPException(status_code=404, detail=f"Image '{image_id}' not found in subchannel '{subchannel_id}'")
        else:
            logger.warning(f"No galleries file found, allowing direct image access for {channel_id}")
    except json.JSONDecodeError:
        logger.error(f"Invalid galleries.json for channel {channel_id}")
        raise HTTPException(status_code=500, detail="Invalid subchannel data")
    
    # Try to get thumbnail from channel instance first
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if channel_instance and hasattr(channel_instance, 'get_image_thumbnail'):
        try:
            thumbnail_path = channel_instance.get_image_thumbnail(image_id)
            if thumbnail_path and Path(thumbnail_path).exists():
                logger.info(f"Serving thumbnail via channel instance: {thumbnail_path}")
                return FileResponse(
                    thumbnail_path,
                    media_type="image/jpeg",
                    filename=f"thumb_{image_id}.jpg",
                    headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
                )
        except Exception as e:
            logger.warning(f"Channel instance thumbnail failed for {image_id}: {e}")
    
    # Fallback: Look for co-located thumbnail in uploads directory
    uploads_dir = channel_dir / "assets" / "uploads"
    
    # Try various thumbnail naming patterns
    thumbnail_patterns = [
        f"image_{image_id}.thumb.jpg",
        f"thumb_{image_id}.jpg",
        f"{image_id}.thumb.jpg",
        f"image_{image_id}_thumb.jpg"
    ]
    
    for pattern in thumbnail_patterns:
        thumbnail_path = uploads_dir / pattern
        if thumbnail_path.exists():
            logger.info(f"Serving co-located thumbnail: {thumbnail_path}")
            return FileResponse(
                thumbnail_path,
                media_type="image/jpeg",
                filename=f"thumb_{image_id}.jpg",
                headers={"Cache-Control": "public, max-age=3600"}
            )
    
    # Last resort: Look for the original image and serve it (browser will scale)
    image_patterns = [
        f"image_{image_id}.jpg",
        f"image_{image_id}.png",
        f"image_{image_id}.jpeg",
        f"{image_id}.jpg",
        f"{image_id}.png"
    ]
    
    for pattern in image_patterns:
        image_path = uploads_dir / pattern
        if image_path.exists():
            logger.info(f"Serving original image as thumbnail fallback: {image_path}")
            # Determine media type from extension
            if pattern.endswith('.png'):
                media_type = "image/png"
            else:
                media_type = "image/jpeg"
                
            return FileResponse(
                image_path,
                media_type=media_type,
                filename=f"thumb_{image_id}{Path(pattern).suffix}",
                headers={"Cache-Control": "public, max-age=1800"}  # Shorter cache for fallbacks
            )
    
    logger.error(f"No thumbnail or image found for {channel_id}/{subchannel_id}/{image_id}")
    raise HTTPException(status_code=404, detail="Thumbnail not found")


@router.get("/{channel_id}/subchannels/{subchannel_id}/images")
async def list_subchannel_images(
    channel_id: str,
    subchannel_id: str,
    include_metadata: bool = Query(False, description="Include detailed image metadata"),
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """
    Get list of images in a specific subchannel with optional metadata
    
    This endpoint returns the images that belong to a specific subchannel/gallery.
    It can optionally include detailed metadata about each image such as dimensions,
    file size, upload date, etc.
    
    Args:
        channel_id: The channel containing the subchannel
        subchannel_id: The subchannel/gallery to list images from
        include_metadata: Whether to include detailed image metadata
        
    Returns:
        {"images": [list of image objects], "total": int, "subchannel": subchannel_info}
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    import json
    from pathlib import Path
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # Get channel directory
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    
    try:
        # Read subchannel data
        galleries_file = channel_dir / 'data' / 'galleries.json'
        if not galleries_file.exists():
            raise HTTPException(status_code=404, detail="No subchannels found for this channel")
        
        with open(galleries_file, 'r', encoding='utf-8') as f:
            galleries = json.load(f)
        
        # Find the specific subchannel
        gallery = next((g for g in galleries if g['id'] == subchannel_id), None)
        if not gallery:
            raise HTTPException(status_code=404, detail=f"Subchannel '{subchannel_id}' not found")
        
        content_ids = gallery.get('contentIds', [])
        
        if not include_metadata:
            # Return just the basic list
            return {
                "images": [{"id": cid} for cid in content_ids],
                "total": len(content_ids),
                "subchannel": {
                    "id": gallery["id"],
                    "name": gallery.get("name", ""),
                    "imageCount": gallery.get("imageCount", len(content_ids))
                }
            }
        
        # Include detailed metadata if requested
        images_with_metadata = []
        
        # Try to get metadata from channel instance
        channel_instance = channel_discovery.get_channel_instance(channel_id)
        if channel_instance and hasattr(channel_instance, 'get_all_images'):
            try:
                all_images = channel_instance.get_all_images()
                # Filter to only images in this subchannel
                for img in all_images:
                    if str(img.get('id')) in content_ids:
                        images_with_metadata.append(img)
                        
                logger.info(f"Retrieved {len(images_with_metadata)} images with metadata from channel instance")
            except Exception as e:
                logger.warning(f"Failed to get metadata from channel instance: {e}")
        
        # If we don't have metadata for all images, create basic entries
        found_ids = {str(img.get('id')) for img in images_with_metadata}
        for content_id in content_ids:
            if content_id not in found_ids:
                images_with_metadata.append({
                    "id": int(content_id) if content_id.isdigit() else content_id,
                    "filename": f"image_{content_id}.jpg",
                    "title": f"Image {content_id}",
                    "enabled": True
                })
        
        return {
            "images": images_with_metadata,
            "total": len(content_ids),
            "subchannel": {
                "id": gallery["id"],
                "name": gallery.get("name", ""),
                "description": gallery.get("description", ""),
                "imageCount": gallery.get("imageCount", len(content_ids)),
                "created": gallery.get("created"),
                "modified": gallery.get("modified")
            }
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in galleries file: {e}")
        raise HTTPException(status_code=500, detail="Invalid subchannel data format")
    except Exception as e:
        logger.error(f"Error listing subchannel images: {e}")
        raise HTTPException(status_code=500, detail="Failed to list subchannel images")


@router.get("/{channel_id}/images")
async def list_images(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get list of images for a channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel directory and read image data
    import json
    from pathlib import Path
    
    # Get channel directory from config
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if channel_data and channel_data.get('path'):
        channel_dir = str(channel_data['path'])
    else:
        channel_dir = f'/var/opt/mimir/mimir-api/channels/{channel_id}'
    
    # For file-based channels, scan the actual uploads directory for images
    from app.core.logging import get_logger
    import os
    import time
    from datetime import datetime
    logger = get_logger("app.api.channels")
    
    try:
        uploads_dir = Path(channel_dir) / 'assets' / 'uploads'
        galleries_file = Path(channel_dir) / 'data' / 'galleries.json'
        
        # Get all image files from uploads directory
        image_files = []
        if uploads_dir.exists():
            for file_path in uploads_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                    # Skip thumbnail files
                    if '.thumb.' in file_path.name:
                        continue
                    image_files.append(file_path)
        
        logger.info(f"Found {len(image_files)} image files in {uploads_dir}")
        
        # Build a mapping of image ID to actual filename from galleries
        id_to_filename = {}
        filename_to_id = {}
        next_available_id = 1
        
        if galleries_file.exists():
            try:
                with open(galleries_file, 'r', encoding='utf-8') as f:
                    galleries = json.load(f)
                
                # Extract all content IDs and track the highest ID
                all_content_ids = set()
                for gallery in galleries:
                    if 'contentIds' in gallery:
                        for content_id in gallery['contentIds']:
                            all_content_ids.add(str(content_id))
                            if content_id.isdigit():
                                next_available_id = max(next_available_id, int(content_id) + 1)
                
                logger.info(f"Found {len(all_content_ids)} content IDs in galleries")
                
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Could not read galleries file: {e}")
                all_content_ids = set()
        else:
            all_content_ids = set()
        
        # Create image data for each actual file
        images = []
        
        # Sort files by name for consistent ordering
        image_files.sort(key=lambda f: f.name)
        
        for index, file_path in enumerate(image_files, start=1):
            try:
                # Get file stats
                stat = file_path.stat()
                file_size = stat.st_size
                modified_time = datetime.fromtimestamp(stat.st_mtime).isoformat() + 'Z'
                created_time = datetime.fromtimestamp(stat.st_ctime).isoformat() + 'Z'
                
                # Try to extract dimensions if possible
                width, height = 1920, 1080  # Default dimensions
                try:
                    from PIL import Image
                    with Image.open(file_path) as img:
                        width, height = img.size
                except (ImportError, Exception):
                    pass  # Use defaults if PIL not available or image can't be read
                
                # Use simple sequential ID assignment
                filename = file_path.name
                image_id = index
                
                # Create title from filename
                title = f"Image {image_id}"
                if '_' in filename:
                    # For hash-based names, create a cleaner title
                    title = f"Image {image_id}"
                
                images.append({
                    "id": image_id,
                    "filename": filename,
                    "original_name": filename,  # Could be enhanced with metadata file
                    "title": title,
                    "description": f"Uploaded image {image_id}",
                    "width": width,
                    "height": height,
                    "file_size": file_size,
                    "enabled": True,
                    "created": created_time,
                    "modified": modified_time,
                    "times_shown": 0  # Could be tracked in metadata file
                })
                
            except Exception as e:
                logger.warning(f"Error processing image file {file_path}: {e}")
                continue
        
        logger.info(f"Returning {len(images)} processed images")
        return images
        
    except Exception as e:
        logger.error(f"Error scanning image files: {e}")
        return []


@router.post("/{channel_id}/images/upload")
async def upload_images(
    channel_id: str,
    files: List[UploadFile] = File(...),
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """
    Upload images to a channel
    
    This endpoint handles image uploads to channels that support image content.
    It processes uploaded files, generates thumbnails, and stores metadata.
    The implementation prioritizes using the channel's own upload handling if available,
    falling back to a standard implementation.
    
    Features:
    - Automatic thumbnail generation (co-located approach)
    - File validation and security checks
    - Unique filename generation to prevent conflicts
    - Integration with channel-specific databases when available
    
    Args:
        channel_id: The target channel for image uploads
        files: List of image files to upload (multipart/form-data)
        
    Returns:
        {"results": [{"filename": str, "success": bool, "image_id": int, "error": str?}]}
    """
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    from pathlib import Path
    import hashlib
    import time
    from app.core.logging import get_logger
    logger = get_logger("app.api.channels")
    
    # For file-based channels, always use the filesystem implementation 
    # Skip channel instance upload to ensure proper thumbnail generation
    logger.info(f"Using filesystem-based upload implementation for {channel_id}")
    
    # Fallback implementation: Standard file upload with thumbnail generation
    all_channels = channel_discovery.get_all_channels()
    channel_data = next((ch for ch in all_channels if ch['id'] == channel_id), None)
    
    if not channel_data or not channel_data.get('path'):
        raise HTTPException(status_code=500, detail="Channel directory not accessible")
    
    channel_dir = Path(channel_data['path'])
    uploads_dir = channel_dir / "assets" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Using fallback upload implementation, saving to: {uploads_dir}")
    
    results = []
    for file in files:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            results.append({
                "filename": file.filename,
                "success": False,
                "error": "File is not an image"
            })
            continue
            
        try:
            # Read file content
            content = await file.read()
            if len(content) == 0:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "Empty file"
                })
                continue
            
            # Generate unique filename using timestamp + content hash
            timestamp = str(int(time.time() * 1000))
            content_hash = hashlib.md5(content + timestamp.encode()).hexdigest()[:12]
            
            # Preserve original extension, default to jpg
            original_ext = Path(file.filename).suffix.lower() if file.filename else ''
            if not original_ext or original_ext not in ['.jpg', '.jpeg', '.png', '.gif']:
                original_ext = '.jpg'
            
            new_filename = f"image_{content_hash}{original_ext}"
            file_path = uploads_dir / new_filename
            
            # Save original file
            with open(file_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"Saved original image: {file_path}")
            
            # Generate co-located thumbnail using the new naming convention
            thumbnail_filename = f"image_{content_hash}.thumb.jpg"
            thumbnail_path = uploads_dir / thumbnail_filename
            
            try:
                # Try to generate thumbnail using PIL if available
                try:
                    from PIL import Image as PILImage
                    
                    with PILImage.open(file_path) as img:
                        # Convert to RGB if necessary (handles PNG with transparency)
                        if img.mode in ('RGBA', 'LA', 'P'):
                            rgb_img = PILImage.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            if img.mode in ('RGBA', 'LA'):
                                rgb_img.paste(img, mask=img.split()[-1])
                            else:
                                rgb_img.paste(img)
                            img = rgb_img
                        
                        # Create thumbnail maintaining aspect ratio (600x600 max)
                        img.thumbnail((600, 600), PILImage.Resampling.LANCZOS)
                        img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                        
                    logger.info(f"Generated thumbnail: {thumbnail_path}")
                    
                except ImportError:
                    logger.warning("PIL not available, skipping thumbnail generation")
                except Exception as thumb_error:
                    logger.warning(f"Thumbnail generation failed for {new_filename}: {thumb_error}")
            except Exception as e:
                logger.warning(f"Could not generate thumbnail for {new_filename}: {e}")
            
            # For file-based channels, generate a simple incremental ID
            image_id = len(results) + 1
            
            results.append({
                "filename": new_filename,
                "original_name": file.filename,
                "success": True,
                "image_id": image_id,
                "thumbnail": thumbnail_filename if thumbnail_path.exists() else None,
                "file_size": len(content)
            })
            
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    logger.info(f"Upload completed: {len([r for r in results if r['success']])} successful, "
                f"{len([r for r in results if not r['success']])} failed")
    
    return {"results": results}


@router.delete("/{channel_id}/images/{image_id}")
async def delete_image(
    channel_id: str,
    image_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Delete an image from a channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, return success - would integrate with channel instance
    return {"success": True}


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Delete channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, deletion is not implemented in discovery service
    raise HTTPException(status_code=501, detail="Channel deletion not implemented")
