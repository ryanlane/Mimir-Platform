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

from app.db.base import SessionLocal
from app.db.models import Scene, DisplayClient
from app.services.mqtt.publisher import mqtt_scene_service
from app.services.display_last_image import display_last_image_store
from app.services.display_image_persistence import DisplayImagePersistenceService
from app.db.base import SessionLocal as _PersistenceSessionLocal
from app.config import settings
from app.services.mdns_discovery import mdns_discovery_service

logger = logging.getLogger(__name__)

try:  # metrics optional; degrade gracefully
    from app.core.metrics import metrics  # type: ignore
    _METRICS = True
except Exception:  # noqa: BLE001
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
                        for (w,h,orientation), display_group in groups.items():
                            request_data: Dict[str, Any] = {
                                "settings": {
                                    "resolution": [w,h],
                                    "orientation": orientation,
                                    "distribution": "new",
                                }
                            }
                            if sc_id:
                                request_data["gallery_id"] = sc_id
                                request_data["settings"]["subChannelId"] = sc_id
                            try:
                                image_response = await plugin.instance.request_image(request_data)
                            except Exception as e:  # noqa: BLE001
                                errors.append(f"channel_request_failed:{ch_id}:{e}")
                                continue
                            if not image_response or not image_response.get("success"):
                                errors.append(f"channel_response_unsuccessful:{ch_id}")
                                continue
                            image_info = image_response
                            image_url = self._convert_image_to_url(image_info)
                            if not image_url:
                                errors.append(f"image_url_conversion_failed:{ch_id}")
                                continue
                            if not sample_url:
                                sample_url = image_url
                                channel_id = ch_id
                                subchannel_id = sc_id
                            for disp in display_group:
                                device_id = disp["device_id"]
                                if not mqtt_scene_service.is_connected():
                                    errors.append("mqtt_not_connected")
                                    break
                                assignment_id = f"display-{device_id[:6]}-{int(time.time())}"
                                try:
                                    success = await mqtt_scene_service.send_display_image(
                                        device_id=device_id,
                                        image_url=image_url,
                                        assignment_id=assignment_id,
                                    )
                                    if success:
                                        total_updated += 1
                                        display_last_image_store.update(
                                            device_id=device_id,
                                            assignment_id=assignment_id,
                                            image_url=image_url,
                                            image_width=w,
                                            image_height=h,
                                            image_format=None,
                                            scene_id=str(scene.id),
                                            subchannel_id=sc_id,
                                        )
                                        try:
                                            with _PersistenceSessionLocal() as p_db:
                                                persistence = DisplayImagePersistenceService(p_db)
                                                persistence.store_distribution_image(
                                                    display_id=device_id,
                                                    scene_id=str(scene.id),
                                                    subchannel_id=sc_id,
                                                    assignment_id=assignment_id,
                                                    image_url=image_url,
                                                    width=w,
                                                    height=h,
                                                    image_format=None,
                                                    source="distribution",
                                                    retain_history=True,
                                                )
                                        except Exception as perr:  # noqa: BLE001
                                            logger.debug("persist_failure device=%s err=%s", device_id, perr)
                                    else:
                                        errors.append(f"mqtt_send_failed:{device_id}")
                                except Exception as send_err:  # noqa: BLE001
                                    errors.append(f"send_exception:{device_id}:{send_err}")

                    status = "ok" if total_updated > 0 else ("skipped" if not errors else "error")
                    skipped_reason = None
                    if status == "skipped" and not total_updated:
                        if not errors:
                            skipped_reason = "no_updates"
                        elif "mqtt_not_connected" in errors:
                            skipped_reason = "mqtt_offline"

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
            except Exception as e:  # noqa: BLE001
                logger.exception("scene.refresh.unexpected scene=%s err=%s", scene_id, e)
                return SceneRefreshResult(
                    scene_id=scene_id,
                    status="error",
                    reason=trigger_reason,
                    errors=[str(e)],
                    duration_ms=int((time.perf_counter()-start)*1000),
                )
            finally:
                if _METRICS:
                    try:
                        # Reuse existing distribution metric semantics for now
                        metrics.distribution_content_assigned(
                            channel_id or "unknown", trigger_reason, ""  # type: ignore[name-defined]
                        )
                    except Exception:  # noqa: BLE001
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
                    except Exception as hash_err:  # noqa: BLE001
                        logger.debug("scene.content_hash.update_failed scene=%s err=%s", scene_id, hash_err)

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
            except Exception as e:  # noqa: BLE001
                logger.debug("collect_discovered.error scene=%s err=%s", scene.id, e)
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


# Global instance
scene_refresh_service = SceneRefreshService()
