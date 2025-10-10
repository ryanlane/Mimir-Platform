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
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import JSONResponse

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
@router.post("/{channel_id}/request-image")
async def request_channel_image(
    channel_id: str,
    request_data: dict[str, Any] | None = None,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Request image generation from a channel plugin (unified path).

    Uses shared normalization logic so scheduler/manual and HTTP produce identical sizing
    and distribution semantics.
    """
    # Validate plugin presence early (shared helper also checks, but we keep API semantics)
    plugin = plugin_discovery.get_plugin(channel_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not plugin.instance:
        raise HTTPException(status_code=503, detail="Channel plugin not loaded")

    from app.services.channel_render_shared import request_channel_image_unified, ChannelRenderError

    payload = request_data or {}
    # Log sanitized inbound payload details for troubleshooting
    try:
        s = payload.get("settings") or {}
        r = s.get("resolution") or payload.get("resolution") or []
        w = int(r[0]) if isinstance(r, (list, tuple)) and len(r) == 2 else None
        h = int(r[1]) if isinstance(r, (list, tuple)) and len(r) == 2 else None
        orient = (s.get("orientation") or payload.get("orientation") or "-")
        dist = (s.get("distribution") or payload.get("distribution") or "-")
        sub = (
            payload.get("gallery_id")
            or s.get("subChannelId")
            or payload.get("subchannel_id")
            or "-"
        )
        opts = payload.get("options") or {}
        ow = opts.get("width") if isinstance(opts, dict) else None
        oh = opts.get("height") if isinstance(opts, dict) else None
        logger.info(
            "channel.request_image.inbound channel=%s w=%s h=%s orientation=%s distribution=%s sub=%s options_wh=%s:%s",
            channel_id,
            w if w is not None else "-",
            h if h is not None else "-",
            orient,
            dist,
            sub,
            ow if isinstance(ow, int) else "-",
            oh if isinstance(oh, int) else "-",
        )
    except Exception:  # pragma: no cover – do not let logging break the endpoint  # noqa: BLE001
        pass
    include_base64 = bool(payload.get("include_base64"))

    try:
        unified = await request_channel_image_unified(channel_id, payload)
    except ChannelRenderError as ce:
        raise HTTPException(status_code=500, detail=str(ce)) from ce

    # Persist bytes into ephemeral store to provide URL (maintain previous contract)
    image_id = str(uuid.uuid4())
    channel_image_store.put(
        channel_id=channel_id,
        image_id=image_id,
        content=unified["bytes"],
        content_type=unified["content_type"],
    )
    base_path = f"/api/channels/{channel_id}/images/{image_id}"

    resp: dict[str, Any] = {
        "imageId": image_id,
        "imageUrl": base_path,
        "contentType": unified["content_type"],
        "width": unified.get("width"),
        "height": unified.get("height"),
        "orientation": unified.get("orientation"),
        "distributionMode": unified.get("distribution_mode"),
        "sha256": unified.get("sha256"),
        "galleryId": unified.get("gallery_id"),
    }
    if include_base64:
        import base64 as _b64  # local import to avoid top-level if unused
        resp["legacyBase64"] = _b64.b64encode(unified["bytes"]).decode("ascii")
    # Optionally include debug headers if processing meta available
    headers = {}
    # Unified helper currently does not expose crop path; if rendering_service stored last meta, we could access here.
    # Placeholder: check for keys that may be added later in unified dict (e.g., processing_path, crop_mode)
    processing_path = unified.get("processing_path")
    crop_mode = unified.get("crop_mode") or unified.get("requested_crop_mode")
    if processing_path:
        headers["X-Processing-Path"] = str(processing_path)
    if crop_mode:
        headers["X-Crop-Mode"] = str(crop_mode)
    if headers:
        return JSONResponse(content=resp, headers=headers)
    return resp


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
