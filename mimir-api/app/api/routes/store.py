"""
Plugin Store API Routes
Registry discovery, available-update checks, and update triggering.
"""
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/store", tags=["store"])

DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/ryanlane/mimir-plugin-registry/main/registry.json"
)

# Simple in-process cache (5 min TTL)
_registry_cache: dict[str, Any] = {"data": None, "ts": 0.0, "url": ""}
_CACHE_TTL = 300


async def _fetch_registry(url: str) -> dict:
    try:
        import httpx
    except ImportError:
        raise HTTPException(502, "httpx is required for registry fetching (pip install httpx)") from None

    # Append a timestamp so CDNs (e.g. raw.githubusercontent.com) don't serve
    # a stale cached response after a registry push.
    bust_url = f"{url}{'&' if '?' in url else '?'}_t={int(time.time())}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(bust_url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Failed to fetch registry from {url}: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(502, f"Registry returned invalid JSON: {exc}") from exc


@router.get("/registry")
async def get_registry(
    url: str = Query(default=DEFAULT_REGISTRY_URL, description="Registry JSON URL"),
):
    """Fetch and cache the plugin registry. Returns the full registry with available plugins."""
    now = time.time()
    if (
        _registry_cache["data"] is not None
        and _registry_cache["url"] == url
        and (now - _registry_cache["ts"]) < _CACHE_TTL
    ):
        return {**_registry_cache["data"], "_cached": True}

    data = await _fetch_registry(url)
    _registry_cache["data"] = data
    _registry_cache["ts"] = now
    _registry_cache["url"] = url
    return {**data, "_cached": False}


@router.post("/registry/refresh")
async def refresh_registry(
    url: str = Query(default=DEFAULT_REGISTRY_URL),
):
    """Force a registry cache bust and re-fetch."""
    _registry_cache["data"] = None
    _registry_cache["ts"] = 0.0
    data = await _fetch_registry(url)
    _registry_cache["data"] = data
    _registry_cache["ts"] = time.time()
    _registry_cache["url"] = url
    return {**data, "_cached": False}


@router.get("/updates")
async def get_available_updates(
    url: str = Query(default=DEFAULT_REGISTRY_URL),
):
    """Compare installed plugin versions against the registry.

    Returns a list of installed plugins that appear in the registry, including
    whether an update is available and whether the plugin can be auto-updated
    (i.e., a git_url is known either from the registry or from install metadata).
    """
    from app.services.plugin_discovery import plugin_discovery_service
    from app.services.plugin_manager import plugin_manager_service

    registry = await get_registry(url=url)
    registry_by_id: dict[str, dict] = {p["id"]: p for p in registry.get("plugins", [])}

    result = []
    for plugin in plugin_discovery_service.get_all_plugins():
        reg = registry_by_id.get(plugin.id)

        # Get the installed version from plugin.json / config.json on disk
        installed_version: str | None = None
        try:
            with open(plugin.config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            installed_version = cfg.get("version")
        except Exception:
            pass

        meta = plugin_manager_service.get_install_meta(plugin.id)
        git_url = (meta or {}).get("git_url") or (reg or {}).get("git_url")

        if reg:
            latest_version = reg.get("version")
            update_available = bool(
                latest_version
                and installed_version
                and latest_version != installed_version
                and git_url
            )
            result.append({
                "plugin_id": plugin.id,
                "name": plugin.name,
                "installed_version": installed_version,
                "latest_version": latest_version,
                "update_available": update_available,
                "can_update": bool(git_url),
                "git_url": git_url,
            })

    pending = sum(1 for r in result if r["update_available"])
    return {"updates": result, "pending_count": pending}
