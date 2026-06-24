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

"""Shared utility functions for the displays domain."""
import ipaddress
import json
import logging
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request

from app.config import settings
from app.db.base import SessionLocal
from app.db.models import DisplayClient, DisplaySceneImage
from app.services.mdns_discovery import mdns_discovery_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------------

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Host / URL resolution helpers
# ---------------------------------------------------------------------------

def extract_hostname_from_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return urlparse(value if "://" in value else f"http://{value}").hostname
    except Exception:
        return None


def build_http_url(host: str, port: int | None) -> str:
    if port in (None, 80):
        return f"http://{host}"
    return f"http://{host}:{port}"


def _host_resolves_to_private_network(hostname: str) -> bool:
    try:
        parsed_ip = ipaddress.ip_address(hostname)
        return parsed_ip.is_private or parsed_ip.is_link_local
    except ValueError:
        pass

    # mDNS names (.local, RFC 6762) are link-local by definition. Accept them
    # without resolving: the server often cannot resolve .local names even
    # though the client that supplied the hint demonstrably can.
    if hostname.rstrip(".").lower().endswith(".local"):
        return True

    try:
        resolved = {
            info[4][0].split("%", 1)[0]
            for info in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    except OSError:
        return False

    if not resolved:
        return False

    try:
        return all(
            ipaddress.ip_address(address).is_private or ipaddress.ip_address(address).is_link_local
            for address in resolved
        )
    except ValueError:
        return False


def _request_host_if_reachable(request: Request | None) -> str | None:
    if not request:
        return None

    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",", 1)[0].strip()
    host_header = (request.headers.get("host") or "").split(",", 1)[0].strip()
    candidates = [
        extract_hostname_from_url(forwarded_host),
        extract_hostname_from_url(host_header),
        request.url.hostname if request.url else None,
    ]
    for host in candidates:
        if settings._is_client_reachable_host(host):
            return host
    return None


def _platform_url_for_clients(request: Request | None) -> str | None:
    request_host = _request_host_if_reachable(request)
    if request_host and request:
        forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip()
        scheme = forwarded_proto or (request.url.scheme if request.url else "http")
        host_header = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",", 1)[0].strip()
        if host_header:
            authority = host_header
        else:
            port = request.url.port if request.url else None
            authority = request_host if port in (None, 80, 443) else f"{request_host}:{port}"
        return f"{scheme}://{authority}".rstrip("/")
    return getattr(settings, "public_base_url", None)


def _mqtt_host_for_clients(request: Request | None) -> str:
    public_base_url = _platform_url_for_clients(request)
    public_base_host = urlparse(public_base_url).hostname if public_base_url else None
    return (
        settings.mqtt_public_host
        or settings.public_mdns_host
        or _request_host_if_reachable(request)
        or public_base_host
        or settings._discover_primary_ipv4()
        or settings.mqtt_broker_host
    )


# ---------------------------------------------------------------------------
# Setup URL normalization (used by provisioning)
# ---------------------------------------------------------------------------

def _normalize_setup_url(raw_url: str) -> str:
    candidate = (raw_url or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="Setup URL is required")

    if "://" not in candidate:
        candidate = f"http://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Setup URL must use http or https")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Setup URL must include a hostname")
    if not settings._is_client_reachable_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="Setup URL must point to a reachable display host")
    if not _host_resolves_to_private_network(parsed.hostname):
        raise HTTPException(status_code=400, detail="Setup URL must resolve to a private network address")

    normalized_path = parsed.path or "/setup"
    if normalized_path == "/":
        normalized_path = "/setup"

    return parsed._replace(path=normalized_path.rstrip("/") or "/setup", params="", query="", fragment="").geturl()


def _provision_url_from_setup_url(setup_url: str) -> str:
    parsed = urlparse(setup_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/setup"):
        provision_path = f"{path[:-6]}/provision" or "/provision"
    elif path in {"", "/"}:
        provision_path = "/provision"
    else:
        provision_path = "/provision"
    return parsed._replace(path=provision_path, params="", query="", fragment="").geturl()


def _normalize_public_host_hint(candidate: str | None) -> str | None:
    host = (candidate or "").strip()
    if not host:
        return None
    normalized = extract_hostname_from_url(host) or host
    if not settings._is_client_reachable_host(normalized):
        return None
    if not _host_resolves_to_private_network(normalized):
        return None
    return normalized


# ---------------------------------------------------------------------------
# Webhook / address helpers
# ---------------------------------------------------------------------------

def _pick_webhook_address(addresses: list[str]) -> str | None:
    for addr in addresses:
        if ":" not in addr:
            return addr
    return addresses[0] if addresses else None


async def _push_runtime_display_config(
    discovered,
    *,
    orientation: str | None = None,
    display_name: str | None = None,
    display_location: str | None = None,
) -> None:
    if not discovered:
        return
    if not discovered.addresses or not discovered.webhook_port:
        raise HTTPException(status_code=409, detail="Display is not currently reachable for runtime configuration")

    addr = _pick_webhook_address(discovered.addresses)
    if not addr:
        raise HTTPException(status_code=409, detail="Display has no usable webhook address")

    payload: dict[str, object] = {"source": "api_display_update"}
    if orientation:
        payload["display_orientation"] = orientation
    if display_name is not None:
        payload["display_name"] = display_name
    if display_location is not None:
        payload["display_location"] = display_location

    url = f"http://{addr}:{discovered.webhook_port}/config"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code >= 300:
                raise HTTPException(status_code=502, detail=f"Display rejected runtime config ({res.status_code})")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Display runtime config failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Orientation helpers
# ---------------------------------------------------------------------------

_ORIENTATION_ALIASES = {
    "landscape": "landscape",
    "landscape_up": "landscape",
    "landscape_normal": "landscape",
    "landscape_inverted": "landscape_inverted",
    "landscape_down": "landscape_inverted",
    "upside_down": "landscape_inverted",
    "portrait": "portrait_right",
    "portrait_up": "portrait_right",
    "portrait_right": "portrait_right",
    "portrait_clockwise": "portrait_right",
    "portrait_down": "portrait_left",
    "portrait_left": "portrait_left",
    "portrait_counterclockwise": "portrait_left",
    "square": "square",
}


def _normalize_display_orientation(value: str | None, *, fallback: str = "landscape") -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return fallback
    return _ORIENTATION_ALIASES.get(raw, fallback)


def _native_dimensions_from_logical(
    width: int | None, height: int | None, orientation: str | None
) -> tuple[int | None, int | None]:
    if not width or not height:
        return width, height
    normalized = _normalize_display_orientation(orientation)
    if normalized.startswith("portrait"):
        return height, width
    return width, height


def _logical_dimensions_for_orientation(
    native_w: int | None, native_h: int | None, orientation: str | None
) -> tuple[int | None, int | None]:
    if not native_w or not native_h:
        return native_w, native_h
    normalized = _normalize_display_orientation(orientation)
    if normalized == "square":
        if native_w != native_h:
            raise HTTPException(status_code=422, detail="Square orientation is only valid for square displays")
        return native_w, native_h
    if normalized.startswith("portrait"):
        return native_h, native_w
    return native_w, native_h


# ---------------------------------------------------------------------------
# Discovery display property extraction
# ---------------------------------------------------------------------------

def _parse_resolution(discovered) -> tuple[int, int]:
    """Attempt to derive width/height from multiple possible sources.

    Sources in priority order:
    1. discovered.properties['resolution'] as 'WIDTHxHEIGHT'
    2. discovered.resolution string 'WIDTHxHEIGHT'
    3. discovered.properties JSON-style arrays (res or native_resolution) serialized
    4. capability style arrays in properties (res, native_resolution) comma/space separated
    5. Fallback to 800x480
    """
    candidates: list[tuple[int, int]] = []
    props = getattr(discovered, 'properties', {}) or {}

    def parse_pair(obj):
        try:
            if isinstance(obj, (list, tuple)) and len(obj) == 2:
                return int(obj[0]), int(obj[1])
            if isinstance(obj, str):
                cleaned = obj.strip().strip('[]')
                if 'x' in cleaned.lower():
                    parts = cleaned.lower().split('x')
                else:
                    cleaned = cleaned.replace(',', ' ')
                    parts = [p for p in cleaned.split() if p]
                if len(parts) == 2:
                    return int(parts[0]), int(parts[1])
        except (ValueError, TypeError):
            return None
        return None

    if props.get('resolution'):
        r = parse_pair(props.get('resolution'))
        if r:
            candidates.append(r)
    if hasattr(discovered, 'resolution') and discovered.resolution:
        r = parse_pair(discovered.resolution)
        if r:
            candidates.append(r)
    for key in ('res', 'native_resolution'):
        if key in props:
            r = parse_pair(props[key])
            if r:
                candidates.append(r)

    for w, h in candidates:
        if w > 0 and h > 0:
            return w, h
    return 800, 480


def _extract_orientation(discovered, width: int | None = None, height: int | None = None) -> str:
    """Determine orientation for a discovered display.

    Precedence:
    1. Explicit property keys (orientation, ori, orientation_mode, orientationMode)
    2. Infer from provided width/height (or parse from resolution attributes if not passed)
       - width == height -> square
       - height > width  -> portrait
       - else -> landscape
    3. Fallback default 'landscape'
    """
    props = getattr(discovered, 'properties', {}) or {}
    for key in ("orientation", "ori", "orientation_mode", "orientationMode"):
        val = props.get(key)
        if val:
            candidate = _normalize_display_orientation(str(val))
            if width is not None and height is not None and width == height:
                return 'square'
            return candidate

    if width is None or height is None:
        try:
            w, h = _parse_resolution(discovered)
        except Exception:  # pragma: no cover - defensive
            w, h = 800, 480
    else:
        w, h = width, height

    if w == h:
        return 'square'
    if h > w:
        return 'portrait_right'
    return 'landscape'


def _extract_supported_formats(discovered) -> list[str] | None:
    """Extract supported image formats from discovered properties.

    Looks at multiple possible keys:
    - properties['formats'] (list or comma/space string)
    - properties['supported_formats']
    - capability style arrays in heartbeat
    """
    props = getattr(discovered, 'properties', {}) or {}
    for key in ('formats', 'supported_formats', 'supportedFormats'):
        if key in props and props[key]:
            val = props[key]
            if isinstance(val, (list, tuple)):
                return [str(v) for v in val]
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(v) for v in parsed]
                except (ValueError, TypeError):
                    pass
                parts = [p.strip() for p in val.replace(';', ',').replace(' ', ',').split(',') if p.strip()]
                if parts:
                    return parts
    return None


# ---------------------------------------------------------------------------
# Discovery display lookup
# ---------------------------------------------------------------------------

def _find_discovered_display(display_id: str, hostname: str | None = None):
    if not mdns_discovery_service.is_running:
        return None
    display = mdns_discovery_service.get_display_by_id(display_id)
    if display:
        return display
    if hostname:
        return mdns_discovery_service.get_display_by_hostname(hostname)
    return None


# ---------------------------------------------------------------------------
# Client config builder
# ---------------------------------------------------------------------------

def _build_client_config(
    display_name: str = "",
    display_location: str = "",
    display_orientation: str | None = None,
) -> dict:
    """Build the config dict pushed inside finalize_registration.

    The display client persists this to device_config.json so the device
    self-configures without manual .env editing after pairing.
    """
    mqtt_host = (
        settings.mqtt_public_host
        or settings.public_mdns_host
        or settings.mqtt_broker_host
    )
    mqtt_port = settings.mqtt_public_port or settings.mqtt_broker_port
    platform_url: str = settings.public_base_url

    cfg: dict = {
        "platform_url": platform_url,
        "display_name": display_name or None,
        "display_location": display_location or None,
        "display_orientation": _normalize_display_orientation(display_orientation) if display_orientation else None,
        "mqtt_host": mqtt_host,
        "mqtt_port": mqtt_port,
    }
    if settings.mqtt_expose_credentials:
        cfg["mqtt_username"] = settings.mqtt_username
        cfg["mqtt_password"] = settings.mqtt_password

    return {k: v for k, v in cfg.items() if v is not None}


# ---------------------------------------------------------------------------
# Response dict builders
# ---------------------------------------------------------------------------

def _build_discovered_display_response(discovered) -> dict:
    """Build dict for DisplayClientResponse from discovered display object."""
    width, height = _parse_resolution(discovered)
    assigned_scene = None
    if getattr(discovered, 'assigned_scene_id', None):
        assigned_scene = {
            'id': discovered.assigned_scene_id,
            'subchannel_id': getattr(discovered, 'assigned_subchannel_id', None)
        }
    supported_formats = _extract_supported_formats(discovered)
    addresses = getattr(discovered, 'addresses', None) or []
    primary_ip = addresses[0] if isinstance(addresses, (list, tuple)) and addresses else None
    return {
        'id': discovered.display_id,
        'name': discovered.display_name,
        'location': discovered.location,
        'hostname': discovered.hostname,
        'webhook_port': discovered.webhook_port,
        'client_version': discovered.client_version or 'unknown',
        'display_type': 'discovered',
        'discovery_method': 'mdns',
        'auto_discovered': True,
        'ip_addresses': list(addresses) if isinstance(addresses, (list, tuple)) else None,
        'ip_address': primary_ip,
        'width': width,
        'height': height,
        'orientation': _extract_orientation(discovered, width, height),
        'supported_formats': supported_formats,
        'redis_distribution': (
            ((getattr(discovered, 'properties', {}) or {}).get('redis_distribution') == 'true')
            or ((getattr(discovered, 'properties', {}) or {}).get('redisDistribution') == 'true')
        ),
        'content_claiming': (
            ((getattr(discovered, 'properties', {}) or {}).get('content_claiming') == 'true')
            or ((getattr(discovered, 'properties', {}) or {}).get('contentClaiming') == 'true')
        ),
        # OTA state (Phase 3)
        'canary': ((getattr(discovered, 'properties', {}) or {}).get('canary') == 'true'),
        'update_status': (getattr(discovered, 'properties', {}) or {}).get('update_status'),
        'update_target': (getattr(discovered, 'properties', {}) or {}).get('update_target'),
        'update_error': (getattr(discovered, 'properties', {}) or {}).get('update_error'),
        'is_online': discovered.is_online,
        'last_seen': discovered.last_seen,
        'assigned_scene_id': assigned_scene,
        'current_content_hash': None,
        'created_at': discovered.discovered_at,
        'updated_at': discovered.last_seen,
        'tags': []
    }


def _build_registered_display_response(client: DisplayClient) -> dict[str, object]:
    """Build dict for DisplayClientResponse from a registered display ORM row."""
    assigned_scene = None
    if getattr(client, 'assigned_scene_id', None):
        assigned_scene = {
            'id': client.assigned_scene_id,
            'subchannel_id': None,
        }

    return {
        'id': str(client.id),
        'name': client.name,
        'location': client.location,
        'description': getattr(client, 'description', None),
        'hostname': client.hostname,
        'webhook_port': client.webhook_port,
        'client_version': client.client_version,
        'display_type': client.display_type,
        'discovery_method': client.discovery_method,
        'auto_discovered': client.auto_discovered,
        'ip_addresses': None,
        'ip_address': None,
        'width': client.width,
        'height': client.height,
        'orientation': client.orientation,
        'supported_formats': None,
        'redis_distribution': client.redis_distribution,
        'content_claiming': client.content_claiming,
        'is_online': client.is_online,
        'last_seen': client.last_seen,
        'assigned_scene_id': assigned_scene,
        'content_variant': client.content_variant,
        'current_content_hash': client.current_content_hash,
        'websocket_connection_id': client.websocket_connection_id,
        'created_at': getattr(client, 'created_at', None),
        'updated_at': getattr(client, 'updated_at', None),
        'tags': getattr(client, 'tags', None),
    }


# ---------------------------------------------------------------------------
# Thumbnail URL builder
# ---------------------------------------------------------------------------

def _build_thumbnail_url(rec: DisplaySceneImage) -> str | None:
    if not rec.thumbnail_path:
        return None
    image_url_base = ""
    if getattr(rec, "image_url", None):
        parsed_image_url = urlparse(rec.image_url)
        if parsed_image_url.scheme and parsed_image_url.netloc:
            image_url_base = f"{parsed_image_url.scheme}://{parsed_image_url.netloc}"
    public_base = image_url_base or getattr(settings, "public_base_url", "")
    media_root_cfg = getattr(settings, "display_images_directory", "display_images")
    media_root = Path(media_root_cfg)
    if not media_root.is_absolute():
        try:
            upload_base = Path(getattr(settings, "upload_dir", ".")).resolve()
        except Exception:  # noqa: BLE001
            upload_base = Path.cwd()
        media_root = (upload_base / media_root).resolve()

    path_obj = Path(rec.thumbnail_path)
    if path_obj.is_absolute():
        try:
            rel = path_obj.resolve().relative_to(media_root)
            return f"{public_base}/media/{rel.as_posix()}" if public_base else f"/media/{rel.as_posix()}"
        except (ValueError, RuntimeError):
            try:
                rel = path_obj.relative_to(Path.cwd())
                return f"{public_base}/{rel.as_posix()}" if public_base else f"/{rel.as_posix()}"
            except (ValueError, RuntimeError):
                return None

    rel_path = rec.thumbnail_path.lstrip("/")
    if rel_path.startswith("media/"):
        return f"{public_base}/{rel_path}" if public_base else f"/{rel_path}"
    return f"{public_base}/media/{rel_path}" if public_base else f"/media/{rel_path}"
