"""Scene Refresh Service

Provides a reusable scene refresh execution path used by both:
- SchedulerWorker (scheduled refreshes)
- ChannelEventConsumer (push-triggered refreshes)

Goals:
- Centralize content acquisition + distribution logic behind a stable contract
- Provide per-scene async locking to avoid overlapping refreshes
- Offer structured result object for metrics/audit
- Allow future extensions: debounce, selective channel refresh, dry-run

This initial implementation focuses on a single-channel assumption (matching current scheduler logic)
and reuses helper methods from SchedulerWorker via light composition to avoid code duplication
until a full extraction/refactor can safely consolidate duplication.
"""
from __future__ import annotations

import asyncio
import logging
import time
import hashlib
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from app.db.base import SessionLocal
from app.db.models import Scene, DisplayClient
from app.services.mqtt.publisher import mqtt_scene_service, MQTTSceneAssignmentPublisher
from app.services.display_last_image import display_last_image_store
from app.services.display_image_persistence import DisplayImagePersistenceService
from app.config import settings
from app.services.mdns_discovery import mdns_discovery_service
from app.services.image_swap import save_swap_image

logger = logging.getLogger(__name__)

# Track last content fingerprint per scene/subchannel to avoid re-sending
# identical content during push/fallback refreshes.
# Key: f"{scene_id}:{subchannel_id or ''}"
_last_scene_fingerprint: Dict[str, str] = {}

_METRICS = False
refresh_counter = None  # type: ignore[assignment]
refresh_duration_counter = None  # type: ignore[assignment]
try:  # metrics optional; keep minimal to avoid circulars
    from app.core.metrics import metrics  # type: ignore
    refresh_counter = getattr(metrics, 'scene_refresh_total', None)  # pre-defined elsewhere ideally
    refresh_duration_counter = getattr(metrics, 'scene_refresh_duration_ms', None)
    _METRICS = any([refresh_counter, refresh_duration_counter])
except ImportError:  # pragma: no cover
    _METRICS = False

# Result dataclass for clarity
@dataclass(slots=True)
class SceneRefreshResult:
    scene_id: str
    status: str  # ok | skipped | error
    reason: str  # trigger reason: scheduler|push|manual|fallback
    content_hash: Optional[str] = None  # placeholder for future hashing
    epoch: Optional[int] = None
    channel_id: Optional[str] = None
    subchannel_id: Optional[str] = None
    displays_updated: int = 0
    errors: List[str] = None  # type: ignore
    duration_ms: int = 0
    skipped_reason: Optional[str] = None
    image_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Ensure errors is list
        if d.get("errors") is None:
            d["errors"] = []
        return d


class SceneRefreshService:
    def __init__(self):
        # Per-scene async locks
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, scene_id: str) -> asyncio.Lock:
        if scene_id not in self._locks:
            self._locks[scene_id] = asyncio.Lock()
        return self._locks[scene_id]

    async def refresh_scene(
        self,
        scene_id: str,
        *,
        trigger_reason: str,
        force: bool = False,
        channel_subset: Optional[List[str]] = None,
    ) -> SceneRefreshResult:
        start = time.perf_counter()
        lock = self._get_lock(scene_id)
        if lock.locked():
            if not force:
                return SceneRefreshResult(
                    scene_id=scene_id,
                    status="skipped",
                    reason=trigger_reason,
                    skipped_reason="locked",
                    duration_ms=int((time.perf_counter()-start)*1000),
                    errors=[],
                )
            # else: fall through and wait
        async with lock:
            try:
                with SessionLocal() as db:
                    scene = db.query(Scene).filter(Scene.id == scene_id).first()
                    if not scene:
                        return SceneRefreshResult(
                            scene_id=scene_id,
                            status="error",
                            reason=trigger_reason,
                            errors=["scene_not_found"],
                            duration_ms=int((time.perf_counter()-start)*1000),
                        )

                    if not scene.channels:
                        return SceneRefreshResult(
                            scene_id=scene_id,
                            status="skipped",
                            reason=trigger_reason,
                            skipped_reason="no_channels",
                            errors=[],
                            duration_ms=int((time.perf_counter()-start)*1000),
                        )

                    # Multi-channel: filter dict entries, optionally subset
                    channel_entries: List[Dict[str, Any]] = [c for c in scene.channels if isinstance(c, dict)]
                    if channel_subset:
                        channel_entries = [c for c in channel_entries if c.get("channel_id") in channel_subset]
                    if not channel_entries:
                        return SceneRefreshResult(
                            scene_id=scene_id,
                            status="skipped",
                            reason=trigger_reason,
                            skipped_reason="no_matching_channels",
                            errors=[],
                            duration_ms=int((time.perf_counter()-start)*1000),
                        )

                    # Collect assigned displays
                    displays = self._collect_assigned_displays(scene)
                    if not displays:
                        return SceneRefreshResult(
                            scene_id=scene_id,
                            status="skipped",
                            reason=trigger_reason,
                            skipped_reason="no_assigned_displays",
                            errors=[],
                            duration_ms=int((time.perf_counter()-start)*1000),
                        )

                    # Group by resolution/orientation
                    groups: Dict[Tuple[int,int,str], List[Dict[str,Any]]] = {}
                    for d in displays:
                        key = (d["width"], d["height"], d["orientation"])
                        groups.setdefault(key, []).append(d)

                    total_updated = 0
                    errors: List[str] = []
                    sample_url: Optional[str] = None
                    # Track first channel/subchannel used for sample
                    channel_id: Optional[str] = None
                    subchannel_id: Optional[str] = None

                    # Lazy import to avoid circular dependency during module import
                    from app.services.plugin_discovery import plugin_discovery_service  # noqa: WPS433

                    for entry in channel_entries:
                        ch_id = entry.get("channel_id")
                        sc_id = entry.get("subchannel_id")
                        if not ch_id:
                            errors.append("missing_channel_id")
                            continue
                        plugin = plugin_discovery_service.get_plugin(ch_id)
                        if not plugin or not plugin.instance:
                            errors.append(f"plugin_not_loaded:{ch_id}")
                            continue
                        # We will evaluate content-gating once on the first group to avoid churn
                        checked_gating = False
                        for (w,h,orientation), display_group in groups.items():
                            request_data: Dict[str, Any] = {
                                "settings": {
                                    "resolution": [w, h],
                                    "orientation": orientation,
                                    "distribution": "new",
                                }
                            }
                            if sc_id:
                                request_data["gallery_id"] = sc_id
                                request_data["settings"]["subChannelId"] = sc_id
                            try:
                                image_response = await plugin.instance.request_image(request_data)
                            except (RuntimeError, ValueError, OSError) as e:  # plugin call safety
                                errors.append(f"channel_request_failed:{ch_id}:{type(e).__name__}")
                                continue
                            if not image_response or not image_response.get("success"):
                                errors.append(f"channel_response_unsuccessful:{ch_id}")
                                continue
                            image_info = image_response
                            # Gating: compute content fingerprint (stable across sizes) and distribution mode
                            if not checked_gating:
                                checked_gating = True
                                scene_key = f"{scene_id}:{sc_id or ''}"
                                fp = (
                                    image_response.get("content_fingerprint")
                                    or (image_response.get("image") or {}).get("content_fingerprint")
                                )
                                dist_mode = (
                                    (image_response.get("image") or {}).get("distribution_mode")
                                    or image_response.get("distribution_mode")
                                )
                                last_fp = _last_scene_fingerprint.get(scene_key)
                                if fp and last_fp and fp == last_fp and not force:
                                    logger.info(
                                        "scene.refresh.skipped unchanged content scene=%s channel=%s sub=%s mode=%s",
                                        scene_id, ch_id, sc_id, dist_mode,
                                    )
                                    return SceneRefreshResult(
                                        scene_id=scene_id,
                                        status="skipped",
                                        reason=trigger_reason,
                                        skipped_reason="unchanged_content",
                                        errors=[],
                                        duration_ms=int((time.perf_counter()-start)*1000),
                                    )
                            raw_bytes = None
                            content_type = None
                            if isinstance(image_info, dict):
                                raw_bytes = image_info.get("bytes")
                                content_type = image_info.get("content_type") or image_info.get("mime_type")
                            image_url = None
                            if raw_bytes:
                                # Will generate per-display URL; sample_url recorded from first display
                                pass
                            else:
                                image_url = self._convert_image_to_url(image_info)
                                if not image_url:
                                    errors.append(f"image_url_conversion_failed:{ch_id}")
                                    continue
                                # Ensure downstream MQTT dedup does not suppress publishes when content changes
                                # but the endpoint URL is stable by appending a cache-busting query param based on
                                # the content fingerprint (fp). This also helps device-side HTTP caches.
                                try:
                                    if 'fp' in locals() and fp:
                                        image_url = self._append_cache_buster(image_url, fp)
                                except Exception:  # pragma: no cover – do not fail refresh on URL tweak issues
                                    pass
                                if not sample_url:
                                    sample_url = image_url
                                    channel_id = ch_id
                                    subchannel_id = sc_id
                            for disp in display_group:
                                device_id = disp["device_id"]
                                # Ensure the underlying publisher loop is running (best-effort).
                                # Do not block refresh if not yet connected; the publisher will queue and send once online.
                                try:
                                    pub = MQTTSceneAssignmentPublisher.get()
                                    if not pub.is_connected():  # type: ignore[attr-defined]
                                        await pub.start()
                                except (RuntimeError, OSError):  # pragma: no cover – resilience
                                    # If singleton not initialized elsewhere, ignore; service path will lazy-start on publish
                                    pass
                                assignment_id = f"display-{device_id[:6]}-{int(time.time())}"
                                try:
                                    logger.info(
                                        "scene.refresh.publish_attempt scene=%s device=%s channel=%s subchannel=%s url=%s assignment=%s",
                                        scene_id,
                                        device_id,
                                        ch_id,
                                        sc_id,
                                        image_url if image_url else ("swap-bytes" if raw_bytes else None),
                                        assignment_id,
                                    )
                                    # If raw bytes present create swap file per display
                                    per_display_url = image_url
                                    swap_path_str: Optional[str] = None
                                    if raw_bytes:
                                        _path, per_display_url, _written = save_swap_image(
                                            scene_id=str(scene_id),
                                            display_id=device_id,
                                            image_bytes=raw_bytes,
                                            content_type=content_type,
                                        )
                                        if not per_display_url:
                                            errors.append(f"swap_save_failed:{device_id}")
                                            logger.debug("scene.refresh.swap_save_failed scene=%s device=%s", scene_id, device_id)
                                            continue
                                        # Apply same cache-busting to per-display URL if fp available
                                        try:
                                            if 'fp' in locals() and fp:
                                                per_display_url = self._append_cache_buster(per_display_url, fp)
                                        except Exception:  # pragma: no cover
                                            pass
                                        if _path:
                                            swap_path_str = str(_path)
                                        if not sample_url:
                                            sample_url = per_display_url
                                            channel_id = ch_id
                                            subchannel_id = sc_id
                                    success = await mqtt_scene_service.send_display_image(
                                        device_id=device_id,
                                        image_url=per_display_url,
                                        assignment_id=assignment_id,
                                    )
                                    if success:
                                        total_updated += 1
                                        logger.info(
                                            "scene.refresh.publish_ok scene=%s device=%s assignment=%s", 
                                            scene_id,
                                            device_id,
                                            assignment_id,
                                        )
                                        display_last_image_store.update(
                                            device_id=device_id,
                                            assignment_id=assignment_id,
                                            image_url=per_display_url,
                                            image_width=w,
                                            image_height=h,
                                            image_format=None,
                                            scene_id=str(scene.id),
                                            subchannel_id=sc_id,
                                            image_path=swap_path_str,
                                        )
                                        # Persistence best-effort; isolate errors
                                        try:
                                            with SessionLocal() as p_db:
                                                DisplayImagePersistenceService(p_db).store_distribution_image(
                                                    display_id=device_id,
                                                    scene_id=str(scene.id),
                                                    subchannel_id=sc_id,
                                                    assignment_id=assignment_id,
                                                    image_url=per_display_url,
                                                    width=w,
                                                    height=h,
                                                    image_format=None,
                                                    source="distribution",
                                                    retain_history=True,
                                                )
                                        except (RuntimeError, ValueError, OSError) as perr:  # persistence non-critical
                                            logger.debug("persist_failure device=%s err=%s", device_id, type(perr).__name__)
                                    else:
                                        errors.append(f"mqtt_send_failed:{device_id}")
                                        logger.warning(
                                            "scene.refresh.publish_failed scene=%s device=%s assignment=%s",
                                            scene_id,
                                            device_id,
                                            assignment_id,
                                        )
                                except (ConnectionError, RuntimeError, OSError) as send_err:  # network/mqtt isolation
                                    errors.append(f"send_exception:{device_id}:{type(send_err).__name__}")
                                    logger.warning(
                                        "scene.refresh.publish_error scene=%s device=%s err=%s", 
                                        scene_id,
                                        device_id,
                                        type(send_err).__name__,
                                    )

                    status = "ok" if total_updated > 0 else ("skipped" if not errors else "error")
                    skipped_reason = None
                    if status == "skipped" and not total_updated:
                        if not errors:
                            skipped_reason = "no_updates"
                        elif "mqtt_not_connected" in errors:
                            skipped_reason = "mqtt_offline"

                    # Update last seen fingerprint (use the last computed one if available)
                    if 'fp' in locals() and fp:
                        _last_scene_fingerprint[f"{scene_id}:{subchannel_id or sc_id or ''}"] = fp

                    return SceneRefreshResult(
                        scene_id=scene_id,
                        status=status,
                        reason=trigger_reason,
                        channel_id=channel_id,
                        subchannel_id=subchannel_id,
                        displays_updated=total_updated,
                        errors=errors,
                        duration_ms=int((time.perf_counter()-start)*1000),
                        skipped_reason=skipped_reason,
                        image_url=sample_url,
                    )
            except (RuntimeError, ValueError, OSError) as e:  # top-level safety
                logger.exception("scene.refresh.unexpected scene=%s err=%s", scene_id, type(e).__name__)
                return SceneRefreshResult(
                    scene_id=scene_id,
                    status="error",
                    reason=trigger_reason,
                    errors=[type(e).__name__],
                    duration_ms=int((time.perf_counter()-start)*1000),
                )
            finally:
                if _METRICS:
                    # Attempt counter increments only if objects exist; ignore failures
                    if refresh_counter:  # type: ignore[truthy-function]
                        try:  # pragma: no cover
                            refresh_counter.add(1)
                        except (RuntimeError, ValueError):  # pragma: no cover
                            pass
                    if refresh_duration_counter:
                        try:  # pragma: no cover
                            refresh_duration_counter.add(int((time.perf_counter()-start)*1000))
                        except (RuntimeError, ValueError):  # pragma: no cover
                            pass
                # Persist content hash if new sample_url was produced
                if 'sample_url' in locals() and sample_url:
                    try:
                        with SessionLocal() as db2:
                            scene_db = db2.query(Scene).filter(Scene.id == scene_id).first()
                            if scene_db:
                                new_hash = hashlib.sha256(f"{channel_id}:{sample_url}".encode()).hexdigest()
                                if scene_db.content_hash != new_hash:
                                    scene_db.content_hash = new_hash
                                    # Increment epoch (initialize if missing)
                                    scene_db.content_epoch = (scene_db.content_epoch or 0) + 1
                                    db2.commit()
                                    logger.debug(
                                        "scene.content_hash.updated scene=%s epoch=%s hash=%s", scene_id, scene_db.content_epoch, new_hash
                                    )
                    except (RuntimeError, ValueError, OSError) as hash_err:  # hash persistence non-critical
                        logger.debug("scene.content_hash.update_failed scene=%s err=%s", scene_id, type(hash_err).__name__)

    # --- Helpers (duplicated conceptually from scheduler worker; refactor later) ---
    def _collect_assigned_displays(self, scene: Scene) -> List[Dict[str, Any]]:
        collected: Dict[str, Dict[str, Any]] = {}
        if mdns_discovery_service.is_running:
            try:
                discovered = mdns_discovery_service.get_discovered_displays()
                for d in discovered:
                    if d.assigned_scene_id == scene.id or d.assigned_scene_id == str(scene.id):
                        w, h = self._parse_resolution_string(d.resolution)
                        collected[d.display_id] = {
                            "device_id": d.hostname or d.display_id,
                            "width": w,
                            "height": h,
                            "orientation": d.properties.get("orientation", "landscape"),
                        }
            except (RuntimeError, ValueError, OSError) as e:  # discovery iteration resilience
                logger.debug("collect_discovered.error scene=%s err=%s", scene.id, type(e).__name__)
        with SessionLocal() as db:
            db_displays = db.query(DisplayClient).filter(
                DisplayClient.assigned_scene_id == scene.id
            ).all()
            for display in db_displays:
                if display.id in collected:
                    continue
                collected[display.id] = {
                    "device_id": display.hostname or display.id,
                    "width": display.width or 800,
                    "height": display.height or 600,
                    "orientation": display.orientation or "landscape",
                }
        return list(collected.values())

    @staticmethod
    def _parse_resolution_string(res_str: Optional[str]):  # type: ignore
        if not res_str or "x" not in res_str:
            return 800, 600
        try:
            w_str, h_str = res_str.lower().split("x", 1)
            w = int(w_str); h = int(h_str)
            if w <= 0 or h <= 0:
                return 800, 600
            return w, h
        except ValueError:
            return 800, 600

    def _convert_image_to_url(self, image_info: Dict[str, Any]) -> Optional[str]:
        # Simplified copy of scheduler conversion (future: factor to shared util)
        base_url = settings.public_base_url
        img_val = image_info.get("image")
        if isinstance(img_val, str):
            if img_val.startswith("/channels/"):
                return f"{base_url}{img_val}"
            # If it's a long string with no slashes early, assume base64 and skip (return None)
            if len(img_val) > 100 and "/" not in img_val[:50]:
                return None
            if img_val.startswith("/"):
                return f"{base_url}/channels/{img_val.lstrip('/')}"
            return f"{base_url}/channels/{img_val}"
        filename = image_info.get("filename")
        if filename:
            return f"{base_url}/channels/photo_frame/uploads/{filename}"
        return None

    @staticmethod
    def _append_cache_buster(url: str, value: str, param: str = "v") -> str:
        """Append or replace a cache-busting query parameter on a URL.

        Args:
            url: The original URL
            value: The cache-busting value (e.g., content fingerprint)
            param: The query parameter name to use (default: "v")

        Returns:
            A URL with the cache-busting parameter applied.
        """
        try:
            parts = urlparse(url)
            query = dict(parse_qsl(parts.query, keep_blank_values=True))
            query[param] = value
            new_query = urlencode(query)
            return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))
        except Exception:
            # If parsing fails (e.g., odd schemeless path), fall back to simple concatenation
            sep = '&' if ('?' in url) else '?'
            return f"{url}{sep}{param}={value}"


# Global instance
scene_refresh_service = SceneRefreshService()
