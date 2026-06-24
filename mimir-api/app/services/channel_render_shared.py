# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Shared Channel Image Render Helper

Provides a single normalization + invocation path for requesting an image
from a channel plugin (embedded) so HTTP routes, scheduler refreshes, and
push/scene refresh logic can all reuse identical behavior.

Goals:
- Normalize incoming request data (resolution, orientation, subchannel/gallery id)
- Provide consistent defaulting logic (800x600, orientation inference)
- Attach distribution mode semantics (explicit 'new' if caller asks, else 'existing')
- Return a normalized dict with keys: success, bytes|image_base64, content_type,
  width, height, orientation, gallery_id, distribution_mode, sha256
- Lightweight and dependency-light to avoid circular imports

This helper intentionally does not perform persistence or distribution; those
concerns remain with higher-level services (scene refresh, scheduler worker, etc.).
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any

from app.core.logging import get_logger
from app.services.plugin_discovery import plugin_discovery_service

logger = get_logger("app.services.channel_render_shared")

DEFAULT_RESOLUTION = (800, 600)
VALID_ORIENTATIONS = {"landscape", "portrait", "square"}

class ChannelRenderError(RuntimeError):
    """Raised when a channel render request fails logically."""


def _derive_resolution(payload: dict[str, Any]) -> tuple[int, int]:
    # Precedence: settings.resolution(list[int]) > options.width/height > root resolution(list[int]) > default
    settings = payload.get("settings") or {}
    if isinstance(settings, dict):
        res = settings.get("resolution")
        if isinstance(res, (list, tuple)) and len(res) == 2 and all(isinstance(v, int) for v in res):
            return int(res[0]), int(res[1])
    options = payload.get("options") or {}
    if isinstance(options, dict):
        w = options.get("width")
        h = options.get("height")
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            return w, h
    root_res = payload.get("resolution")
    if isinstance(root_res, (list, tuple)) and len(root_res) == 2 and all(isinstance(v, int) for v in root_res):
        return int(root_res[0]), int(root_res[1])
    return DEFAULT_RESOLUTION


def _derive_orientation(payload: dict[str, Any], width: int, height: int) -> str:
    settings = payload.get("settings") or {}
    orient = None
    if isinstance(settings, dict):
        orient = settings.get("orientation")
    if not orient:
        orient = payload.get("orientation")
    if isinstance(orient, str):
        orient_l = orient.lower()
        if orient_l in VALID_ORIENTATIONS:
            return orient_l
    # Infer
    if width == height:
        return "square"
    return "portrait" if height > width else "landscape"


def _derive_gallery(payload: dict[str, Any]) -> str | None:
    # Accept several keys for flexibility
    for key in ("gallery_id", "subChannelId", "subchannel_id"):
        val = payload.get(key) or (payload.get("settings") or {}).get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _inject_normalized_settings(payload: dict[str, Any], width: int, height: int, orientation: str, gallery_id: str | None) -> dict[str, Any]:
    # Copy to avoid mutating caller payload unexpectedly
    data = dict(payload)
    settings = dict(data.get("settings") or {})
    settings.setdefault("resolution", [width, height])
    settings.setdefault("orientation", orientation)
    if gallery_id:
        settings.setdefault("subChannelId", gallery_id)
    # Distribution: default to 'existing' unless caller explicitly set 'distribution'='new'
    if settings.get("distribution") not in ("new", "existing", "cached"):
        settings["distribution"] = "existing"
    data["settings"] = settings
    # Preserve caller-provided options only; do NOT inject width/height by default
    # Some channels interpret options.width/height differently (fit vs crop),
    # while settings.resolution is the source of truth for sizing.
    if "options" in data and isinstance(data["options"], dict):
        data["options"] = dict(data["options"])  # shallow copy
    # Provide gallery id root-level for plugins expecting that
    if gallery_id:
        data.setdefault("gallery_id", gallery_id)
    return data


def _compute_sha256(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()


async def request_channel_image_unified(channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Unified channel image request.

    Returns normalized result dict. Raises ChannelRenderError for logical failures.
    """
    plugin = plugin_discovery_service.get_plugin(channel_id)
    if not plugin or not plugin.instance:
        raise ChannelRenderError(f"Channel {channel_id} not found or not loaded")

    width, height = _derive_resolution(payload)
    orientation = _derive_orientation(payload, width, height)
    # Normalize resolution to match the chosen orientation
    if orientation == "portrait" and width > height:
        width, height = height, width
    elif orientation == "landscape" and height > width:
        width, height = height, width
    elif orientation == "square":
        m = min(width, height)
        width, height = m, m
    # Warn if the provided orientation conflicts with inferred aspect ratio
    explicit_orient = None
    s = payload.get("settings") or {}
    if isinstance(s, dict):
        explicit_orient = s.get("orientation") or payload.get("orientation")
    if isinstance(explicit_orient, str):
        eo = explicit_orient.lower()
        inferred = "square" if width == height else ("portrait" if height > width else "landscape")
        if eo in VALID_ORIENTATIONS and eo != inferred:
            logger.warning(
                "channel.render.conflicting_orientation channel=%s requested=%s inferred=%s w=%s h=%s",
                channel_id,
                eo,
                inferred,
                width,
                height,
            )
    gallery_id = _derive_gallery(payload)

    normalized_payload = _inject_normalized_settings(payload, width, height, orientation, gallery_id)

    # Log normalized request details (sanitized) for troubleshooting
    try:
        s = normalized_payload.get("settings") or {}
        dist = s.get("distribution")
        opts = payload.get("options") or {}
        ow = opts.get("width") if isinstance(opts, dict) else None
        oh = opts.get("height") if isinstance(opts, dict) else None
        logger.info(
            "channel.render.normalized channel=%s w=%s h=%s orientation=%s distribution=%s gallery=%s options_wh=%s:%s",
            channel_id,
            width,
            height,
            orientation,
            dist,
            gallery_id or "-",
            ow if isinstance(ow, int) else "-",
            oh if isinstance(oh, int) else "-",
        )
    except Exception:  # pragma: no cover – avoid logging failures  # noqa: BLE001
        pass

    try:
        raw_result = await plugin.instance.request_image(normalized_payload)
    except Exception as e:  # noqa: BLE001
        logger.error("unified.render.error channel=%s err=%s", channel_id, e)
        raise ChannelRenderError(str(e)) from e

    # Normalize outputs
    content_bytes: bytes | None = None
    content_type = "image/jpeg"
    b64_payload: str | None = None
    extra: dict[str, Any] = {}

    if isinstance(raw_result, dict):
        # Common plugin shape: may include success flag
        extra = {k: v for k, v in raw_result.items() if k not in {"image", "image_base64", "bytes", "content_type"}}
        if isinstance(raw_result.get("bytes"), (bytes, bytearray)):
            content_bytes = bytes(raw_result["bytes"])  # type: ignore[index]
        elif isinstance(raw_result.get("image"), str):
            b64_payload = raw_result["image"]  # type: ignore[index]
        elif isinstance(raw_result.get("image_base64"), str):
            b64_payload = raw_result["image_base64"]  # type: ignore[index]
        content_type = raw_result.get("content_type", content_type)  # type: ignore[arg-type]
    elif isinstance(raw_result, (bytes, bytearray)):
        content_bytes = bytes(raw_result)
    elif isinstance(raw_result, str):
        # Could be data URI or plain base64
        if raw_result.startswith("data:image") and ";base64," in raw_result:
            prefix, b64_part = raw_result.split(",", 1)
            try:
                content_type = prefix.split(":", 1)[1].split(";", 1)[0]
            except IndexError:
                pass
            b64_payload = b64_part
        else:
            b64_payload = raw_result
    else:
        raise ChannelRenderError("Unsupported plugin image result format")

    if b64_payload and not content_bytes:
        try:
            content_bytes = base64.b64decode(b64_payload, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ChannelRenderError("Failed to decode base64 image from plugin") from exc

    if not content_bytes:
        raise ChannelRenderError("No image content produced by plugin")

    # Sniff content type if default
    if content_type == "image/jpeg" and len(content_bytes) >= 4:
        if content_bytes.startswith(b"\x89PNG"):
            content_type = "image/png"
        elif content_bytes[0:2] == b"\xff\xd8":
            content_type = "image/jpeg"

    sha256 = _compute_sha256(content_bytes)

    # Summarize result
    try:
        logger.info(
            "channel.render.result channel=%s type=%s bytes=%s sha256=%s",
            channel_id,
            content_type,
            len(content_bytes),
            sha256[:12],
        )
    except Exception:  # pragma: no cover  # noqa: BLE001
        pass

    return {
        "success": True,
        "bytes": content_bytes,
        "content_type": content_type,
        "width": width,
        "height": height,
        "orientation": orientation,
        "gallery_id": gallery_id,
        "distribution_mode": (normalized_payload.get("settings") or {}).get("distribution"),
        "sha256": sha256,
        **extra,
    }
