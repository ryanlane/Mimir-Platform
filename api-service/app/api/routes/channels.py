"""
Channel Plugin API Routes
FastAPI router for the new embedded plugin architecture

This file implements the 4-endpoint plugin architecture:
1. GET /api/channels/ - List available channel plugins
2. GET /api/channels/{channel_id}/manifest - Get channel capabilities 
3. GET /api/channels/{channel_id}/health - Check channel health
4. POST /api/channels/{channel_id}/request_image - Request image generation

Channel plugins are loaded directly into the main API process and their routes
are mounted at /api/channels/{channel_id}/* by the plugin discovery service.
"""
import base64
import uuid
from fastapi import APIRouter, HTTPException, Depends, Response
from typing import Dict, Any, Optional

from app.services.deps import get_plugin_discovery_service
from app.services.plugin_discovery import PluginDiscoveryService
from app.core.logging import get_logger
from app.services.channel_image_store import channel_image_store

logger = get_logger("app.api.channels")
router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
async def list_channels(
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """List all available channel plugins"""
    plugins = plugin_discovery.get_all_plugins()
    
    channels = []
    for plugin in plugins:
        channels.append({
            "id": plugin.id,
            "name": plugin.name,
            "description": plugin.description,
            "icon": plugin.icon
        })
    
    return {
        "channels": channels,
        "total": len(channels)
    }


@router.get("/{channel_id}/manifest")
async def get_channel_manifest(
    channel_id: str,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Get channel manifest with current capabilities"""
    manifest = await plugin_discovery.get_plugin_manifest(channel_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Channel not found or unavailable")
    
    return manifest


@router.get("/{channel_id}/health")
async def get_channel_health(
    channel_id: str,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Get channel health status"""
    plugin = plugin_discovery.get_plugin(channel_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For embedded plugins, check if instance is available and working
    healthy = plugin.instance is not None
    
    return {
        "channelId": channel_id,
        "name": plugin.name,
        "healthy": healthy,
        "lastCheck": plugin.last_health_check,
        "pluginPath": plugin.plugin_path
    }


@router.post("/{channel_id}/request_image")
async def request_channel_image(
    channel_id: str,
    request_data: Optional[Dict[str, Any]] = None,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Request image generation from a channel plugin.

    Returns a JSON payload containing a short-lived image URL instead of embedding
    the potentially large base64 blob directly in follow-up request paths.

    Response example:
        {
          "imageId": "550e8400-e29b-41d4-a716-446655440000",
          "imageUrl": "/api/channels/example/images/550e8400-e29b-41d4-a716-446655440000",
          "contentType": "image/jpeg",
          "legacyBase64": "<only-present-if-include_base64=true was requested>"
        }
    """
    plugin = plugin_discovery.get_plugin(channel_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Channel not found")

    if not plugin.instance:
        raise HTTPException(status_code=503, detail="Channel plugin not loaded")

    data = request_data or {}
    include_base64 = bool(data.get("include_base64"))

    try:
        raw_result = await plugin.instance.request_image(data)
    except Exception as e:  # noqa: BLE001
        logger.error("Error generating image from plugin %s: %s", channel_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)}") from e

    # The plugin might return:
    #   * raw base64 string
    #   * bytes
    #   * dict with keys { image / image_base64 / bytes / content_type }
    b64_payload: Optional[str] = None
    content_bytes: Optional[bytes] = None
    content_type = "image/jpeg"  # default fallback

    try:
        if isinstance(raw_result, dict):
            if isinstance(raw_result.get("bytes"), (bytes, bytearray)):
                content_bytes = bytes(raw_result["bytes"])
            elif isinstance(raw_result.get("image"), str):
                b64_payload = raw_result["image"]
            elif isinstance(raw_result.get("image_base64"), str):
                b64_payload = raw_result["image_base64"]
            content_type = raw_result.get("content_type", content_type)
        elif isinstance(raw_result, (bytes, bytearray)):
            content_bytes = bytes(raw_result)
        elif isinstance(raw_result, str):
            # Could be a data URI or plain base64
            if raw_result.startswith("data:image") and ";base64," in raw_result:
                # Extract mime + base64
                prefix, b64_payload = raw_result.split(",", 1)
                try:
                    content_type = prefix.split(":", 1)[1].split(";", 1)[0]
                except IndexError:
                    pass
            else:
                b64_payload = raw_result
        else:
            raise ValueError("Unsupported image result format from plugin")

        if b64_payload and not content_bytes:
            try:
                content_bytes = base64.b64decode(b64_payload, validate=True)
            except Exception:  # noqa: BLE001
                raise ValueError("Failed to decode base64 image from plugin")

        if not content_bytes:
            raise ValueError("No image content produced by plugin")

        # Simple format sniffing to adjust content-type if default
        if content_type == "image/jpeg" and len(content_bytes) >= 4:
            if content_bytes.startswith(b"\x89PNG"):
                content_type = "image/png"
            elif content_bytes[0:2] == b"\xff\xd8":
                content_type = "image/jpeg"

        image_id = str(uuid.uuid4())
        channel_image_store.put(channel_id=channel_id, image_id=image_id, content=content_bytes, content_type=content_type)

        base_path = f"/api/channels/{channel_id}/images/{image_id}"
        response: Dict[str, Any] = {
            "imageId": image_id,
            "imageUrl": base_path,
            "contentType": content_type,
        }

        if include_base64 and b64_payload:
            response["legacyBase64"] = b64_payload

        return response
    except ValueError as ve:  # Input/format issues
        logger.warning("Invalid image output from plugin %s: %s", channel_id, ve)
        raise HTTPException(status_code=422, detail=str(ve)) from ve
    except Exception as e:  # noqa: BLE001
        logger.error("Unhandled error processing image for %s: %s", channel_id, e)
        raise HTTPException(status_code=500, detail="Internal error storing image") from e


@router.get("/{channel_id}/images/{image_id}")
async def get_channel_image(
    channel_id: str,
    image_id: str,
):
    """Return previously generated channel image by ID.

    Images are ephemeral; a 404 will be returned if expired or missing.
    """
    record = channel_image_store.get(channel_id, image_id)
    if not record:
        raise HTTPException(status_code=404, detail="Image not found or expired")
    return Response(content=record.content, media_type=record.content_type)


# Embedded plugins don't need a general proxy endpoint
# All plugin functionality is exposed through their specific routes
# which are mounted by the plugin discovery service
