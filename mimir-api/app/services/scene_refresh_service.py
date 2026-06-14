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
import hashlib
import json as _json
import logging
import time
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import (
    Any,  # NOTE: legacy typing kept for untouched sections; new edits prefer PEP 585
)
from urllib import error as _urlerr
from urllib import request as _urlreq
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    from PIL import Image  # type: ignore
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

from app.config import settings
from app.db.base import SessionLocal
from app.db.models import DisplayClient, Scene
from app.services.display_image_persistence import DisplayImagePersistenceService
from app.services.display_last_image import display_last_image_store
from app.services.image_swap import save_swap_image
from app.services.mdns_discovery import mdns_discovery_service
from app.services.mqtt.publisher import MQTTSceneAssignmentPublisher, mqtt_scene_service

logger = logging.getLogger(__name__)

# Track last content fingerprint per scene/subchannel to avoid re-sending
# identical content during push/fallback refreshes.
# Key: f"{scene_id}:{subchannel_id or ''}"
_last_scene_fingerprint: dict[str, str] = {}

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
    content_hash: str | None = None  # placeholder for future hashing
    epoch: int | None = None
    channel_id: str | None = None
    subchannel_id: str | None = None
    displays_updated: int = 0
    errors: list[str] = None  # type: ignore
    duration_ms: int = 0
    skipped_reason: str | None = None
    image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Ensure errors is list
        if d.get("errors") is None:
            d["errors"] = []
        return d


class SceneRefreshService:
    def __init__(self):
        # Per-scene async locks
        self._locks: dict[str, asyncio.Lock] = {}

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
        channel_subset: list[str] | None = None,
        target_devices: list[str] | None = None,
        public_base_url_override: str | None = None,
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
                    channel_entries: list[dict[str, Any]] = [c for c in scene.channels if isinstance(c, dict)]
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
                    try:
                        logger.info(
                            "scene.refresh.request scene=%s trigger=%s assigned=%s targets=%s subset=%s force=%s",
                            scene_id,
                            trigger_reason,
                            len(displays),
                            len(target_devices) if target_devices else 0,
                            len(channel_subset) if channel_subset else 0,
                            force,
                        )
                        logger.debug(
                            "scene.refresh.assigned_devices scene=%s devices=%s",
                            scene_id,
                            [d.get("device_id") for d in displays],
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    # If targeting specific device(s), filter here
                    if target_devices:
                        allow = set(target_devices)
                        displays = [d for d in displays if d.get("device_id") in allow]
                        try:
                            logger.info(
                                "scene.refresh.filtered_devices scene=%s count=%s targets=%s",
                                scene_id,
                                len(displays),
                                list(allow),
                            )
                            logger.debug(
                                "scene.refresh.filtered_list scene=%s devices=%s",
                                scene_id,
                                [d.get("device_id") for d in displays],
                            )
                        except Exception:  # noqa: BLE001
                            pass
                        if not displays:
                            return SceneRefreshResult(
                                scene_id=scene_id,
                                status="skipped",
                                reason=trigger_reason,
                                skipped_reason="no_matching_target",
                                errors=[],
                                duration_ms=int((time.perf_counter()-start)*1000),
                            )
                    if not displays:
                        return SceneRefreshResult(
                            scene_id=scene_id,
                            status="skipped",
                            reason=trigger_reason,
                            skipped_reason="no_assigned_displays",
                            errors=[],
                            duration_ms=int((time.perf_counter()-start)*1000),
                        )

                    # Group by resolution/orientation (infer orientation from aspect to avoid mismatches)
                    groups: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
                    for d in displays:
                        w, h = d["width"], d["height"]
                        inferred_orient = "square" if w == h else ("portrait" if h > w else "landscape")
                        key = (w, h, inferred_orient)
                        groups.setdefault(key, []).append({**d, "orientation": inferred_orient})

                    total_updated = 0
                    errors: list[str] = []
                    sample_url: str | None = None
                    # Track first channel/subchannel used for sample
                    channel_id: str | None = None
                    subchannel_id: str | None = None

                    # Local lazy import to avoid circular import on startup
                    from app.services.plugin_discovery import (
                        plugin_discovery_service,  # noqa: WPS433
                    )

                    for entry in channel_entries:
                        ch_id = entry.get("channel_id")
                        sc_id = entry.get("subchannel_id")
                        if not ch_id:
                            errors.append("missing_channel_id")
                            continue
                        # Validate plugin availability early (unified helper will also validate)
                        plugin = plugin_discovery_service.get_plugin(ch_id)
                        if not plugin or not plugin.instance:  # defensive double-check
                            errors.append(f"plugin_not_loaded:{ch_id}")
                            continue
                        # Determine fetch strategy: mirror (one fetch per group) vs sequential (per-device)
                        distribution_mode = (getattr(scene, "distribution_mode", "mirror") or "mirror").lower()
                        # Evaluate content-gating once per scene execution
                        checked_gating = False

                        if distribution_mode == "sequential":
                            # Per-device HTTP requests
                            for (w, h, orientation), display_group in groups.items():
                                for disp in display_group:
                                    logger.info(
                                        "scene.refresh.device_request scene=%s channel=%s sub=%s device=%s w=%s h=%s orient=%s distribution=%s",
                                        scene_id,
                                        ch_id,
                                        sc_id or "-",
                                        disp.get("device_id"),
                                        w,
                                        h,
                                        orientation,
                                        "new",
                                    )
                                    request_payload: dict[str, Any] = {
                                        "settings": {
                                            "resolution": [w, h],
                                            "orientation": orientation,
                                            "distribution": "new",
                                        }
                                    }
                                    if sc_id:
                                        request_payload["gallery_id"] = sc_id
                                        request_payload["settings"]["subChannelId"] = sc_id
                                    try:
                                        raw_bytes, content_type, fp = await self._request_channel_image_http(ch_id, request_payload)
                                    except RuntimeError as e:
                                        errors.append(f"channel_request_failed:{ch_id}:{type(e).__name__}")
                                        continue

                                    # Gating once using first device's fingerprint
                                    if not checked_gating:
                                        checked_gating = True
                                        scene_key = f"{scene_id}:{sc_id or ''}"
                                        if not fp:
                                            try:
                                                fp = hashlib.sha256(raw_bytes).hexdigest()
                                            except (ValueError, TypeError):
                                                fp = None
                                        last_fp = _last_scene_fingerprint.get(scene_key)
                                        if fp and last_fp and fp == last_fp and not force:
                                            logger.info(
                                                "scene.refresh.skipped unchanged content scene=%s channel=%s sub=%s mode=%s",
                                                scene_id, ch_id, sc_id, "new",
                                            )
                                            return SceneRefreshResult(
                                                scene_id=scene_id,
                                                status="skipped",
                                                reason=trigger_reason,
                                                skipped_reason="unchanged_content",
                                                errors=[],
                                                duration_ms=int((time.perf_counter()-start)*1000),
                                            )

                                    # Optional: decode to log size mismatch only; never modify bytes
                                    if raw_bytes and Image is not None:
                                        try:
                                            with Image.open(BytesIO(raw_bytes)) as im:
                                                actual_w, actual_h = im.size
                                                if (actual_w, actual_h) != (w, h):
                                                    logger.info(
                                                        "scene.refresh.size_mismatch scene=%s channel=%s sub=%s requested=%sx%s actual=%sx%s",
                                                        scene_id,
                                                        ch_id,
                                                        sc_id,
                                                        w,
                                                        h,
                                                        actual_w,
                                                        actual_h,
                                                    )
                                        except (OSError, ValueError):
                                            pass

                                    # Publish per-device
                                    device_id = disp["device_id"]
                                    try:
                                        pub = MQTTSceneAssignmentPublisher.get()
                                        if not pub.is_connected():  # type: ignore[attr-defined]
                                            await pub.start()
                                    except (RuntimeError, OSError):
                                        pass
                                    assignment_id = f"display-{device_id[:6]}-{int(time.time())}"
                                    try:
                                        logger.info(
                                            "scene.refresh.publish_attempt scene=%s device=%s channel=%s subchannel=%s url=%s assignment=%s",
                                            scene_id,
                                            device_id,
                                            ch_id,
                                            sc_id,
                                            "swap-bytes",
                                            assignment_id,
                                        )
                                        _path, per_display_url, _written = save_swap_image(
                                            scene_id=str(scene_id),
                                            display_id=device_id,
                                            image_bytes=raw_bytes,
                                            content_type=content_type,
                                            public_base_url=public_base_url_override,
                                        )
                                        if not per_display_url:
                                            errors.append(f"swap_save_failed:{device_id}")
                                            continue
                                        if fp:
                                            try:
                                                per_display_url = self._append_cache_buster(per_display_url, fp)
                                            except (ValueError, TypeError):
                                                pass
                                        success = await mqtt_scene_service.send_display_image(
                                            device_id=device_id,
                                            image_url=per_display_url,
                                            assignment_id=assignment_id,
                                        )
                                        if success:
                                            total_updated += 1
                                            if not sample_url:
                                                sample_url = per_display_url
                                                channel_id = ch_id
                                                subchannel_id = sc_id
                                            display_last_image_store.update(
                                                device_id=device_id,
                                                assignment_id=assignment_id,
                                                image_url=per_display_url,
                                                image_width=w,
                                                image_height=h,
                                                image_format=None,
                                                scene_id=str(scene.id),
                                                subchannel_id=sc_id,
                                                image_path=str(_path) if _path else None,
                                            )
                                            try:
                                                with SessionLocal() as p_db:
                                                    DisplayImagePersistenceService(p_db).store_distribution_image(
                                                        display_id=device_id,
                                                        scene_id=str(scene.id),
                                                        subchannel_id=sc_id,
                                                        assignment_id=assignment_id,
                                                        image_url=per_display_url,
                                                        local_source_path=str(_path) if _path else None,
                                                        width=w,
                                                        height=h,
                                                        image_format=None,
                                                        source="distribution",
                                                        retain_history=True,
                                                    )
                                            except Exception:  # noqa: BLE001
                                                pass
                                        else:
                                            errors.append(f"mqtt_send_failed:{device_id}")
                                    except (ConnectionError, RuntimeError, OSError) as send_err:
                                        errors.append(f"send_exception:{device_id}:{type(send_err).__name__}")
                            # End sequential loop
                        else:
                            # Mirror mode: one HTTP request per group, fan-out to displays
                            for (w, h, orientation), display_group in groups.items():
                                logger.info(
                                    "scene.refresh.group_request scene=%s channel=%s sub=%s w=%s h=%s orient=%s distribution=%s count=%s",
                                    scene_id,
                                    ch_id,
                                    sc_id or "-",
                                    w,
                                    h,
                                    orientation,
                                    "new",
                                    len(display_group),
                                )
                                request_payload: dict[str, Any] = {
                                    "settings": {
                                        "resolution": [w, h],
                                        "orientation": orientation,
                                        "distribution": "new",
                                    }
                                }
                                if sc_id:
                                    request_payload["gallery_id"] = sc_id
                                    request_payload["settings"]["subChannelId"] = sc_id
                                try:
                                    raw_bytes, content_type, fp = await self._request_channel_image_http(ch_id, request_payload)
                                except RuntimeError as e:
                                    errors.append(f"channel_request_failed:{ch_id}:{type(e).__name__}")
                                    continue

                                # Gating once for scene on first successful fetch
                                if not checked_gating:
                                    checked_gating = True
                                    scene_key = f"{scene_id}:{sc_id or ''}"
                                    if not fp:
                                        try:
                                            fp = hashlib.sha256(raw_bytes).hexdigest()
                                        except (ValueError, TypeError):
                                            fp = None
                                    last_fp = _last_scene_fingerprint.get(scene_key)
                                    if fp and last_fp and fp == last_fp and not force:
                                        logger.info(
                                            "scene.refresh.skipped unchanged content scene=%s channel=%s sub=%s mode=%s",
                                            scene_id, ch_id, sc_id, "new",
                                        )
                                        return SceneRefreshResult(
                                            scene_id=scene_id,
                                            status="skipped",
                                            reason=trigger_reason,
                                            skipped_reason="unchanged_content",
                                            errors=[],
                                            duration_ms=int((time.perf_counter()-start)*1000),
                                        )

                                # Optional: decode to log size mismatch only; never modify bytes
                                if raw_bytes and Image is not None:
                                    try:
                                        with Image.open(BytesIO(raw_bytes)) as im:
                                            actual_w, actual_h = im.size
                                            if (actual_w, actual_h) != (w, h):
                                                logger.info(
                                                    "scene.refresh.size_mismatch scene=%s channel=%s sub=%s requested=%sx%s actual=%sx%s",
                                                    scene_id,
                                                    ch_id,
                                                    sc_id,
                                                    w,
                                                    h,
                                                    actual_w,
                                                    actual_h,
                                                )
                                    except (OSError, ValueError):
                                        pass

                                # Fan-out to displays in this group
                                for disp in display_group:
                                    device_id = disp["device_id"]
                                    try:
                                        pub = MQTTSceneAssignmentPublisher.get()
                                        if not pub.is_connected():  # type: ignore[attr-defined]
                                            await pub.start()
                                    except (RuntimeError, OSError):
                                        pass
                                    assignment_id = f"display-{device_id[:6]}-{int(time.time())}"
                                    try:
                                        logger.info(
                                            "scene.refresh.publish_attempt scene=%s device=%s channel=%s subchannel=%s url=%s assignment=%s",
                                            scene_id,
                                            device_id,
                                            ch_id,
                                            sc_id,
                                            "swap-bytes",
                                            assignment_id,
                                        )
                                        _path, per_display_url, _written = save_swap_image(
                                            scene_id=str(scene_id),
                                            display_id=device_id,
                                            image_bytes=raw_bytes,
                                            content_type=content_type,
                                            public_base_url=public_base_url_override,
                                        )
                                        if not per_display_url:
                                            errors.append(f"swap_save_failed:{device_id}")
                                            continue
                                        if fp:
                                            try:
                                                per_display_url = self._append_cache_buster(per_display_url, fp)
                                            except (ValueError, TypeError):
                                                pass
                                        success = await mqtt_scene_service.send_display_image(
                                            device_id=device_id,
                                            image_url=per_display_url,
                                            assignment_id=assignment_id,
                                        )
                                        if success:
                                            total_updated += 1
                                            if not sample_url:
                                                sample_url = per_display_url
                                                channel_id = ch_id
                                                subchannel_id = sc_id
                                            display_last_image_store.update(
                                                device_id=device_id,
                                                assignment_id=assignment_id,
                                                image_url=per_display_url,
                                                image_width=w,
                                                image_height=h,
                                                image_format=None,
                                                scene_id=str(scene.id),
                                                subchannel_id=sc_id,
                                                image_path=str(_path) if _path else None,
                                            )
                                            try:
                                                with SessionLocal() as p_db:
                                                    DisplayImagePersistenceService(p_db).store_distribution_image(
                                                        display_id=device_id,
                                                        scene_id=str(scene.id),
                                                        subchannel_id=sc_id,
                                                        assignment_id=assignment_id,
                                                        image_url=per_display_url,
                                                        local_source_path=str(_path) if _path else None,
                                                        width=w,
                                                        height=h,
                                                        image_format=None,
                                                        source="distribution",
                                                        retain_history=True,
                                                    )
                                            except (RuntimeError, ValueError, OSError):
                                                pass
                                        else:
                                            errors.append(f"mqtt_send_failed:{device_id}")
                                    except (ConnectionError, RuntimeError, OSError) as send_err:
                                        errors.append(f"send_exception:{device_id}:{type(send_err).__name__}")

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
    def _collect_assigned_displays(self, scene: Scene) -> list[dict[str, Any]]:
        collected: dict[str, dict[str, Any]] = {}
        if mdns_discovery_service.is_running:
            try:
                discovered = mdns_discovery_service.get_discovered_displays()
                for d in discovered:
                    if d.assigned_scene_id == scene.id or d.assigned_scene_id == str(scene.id):
                        props = getattr(d, "properties", {}) or {}
                        resolution_value = (
                            d.resolution
                            or props.get("resolution")
                            or props.get("native_resolution")
                        )
                        w, h = self._parse_resolution_string(resolution_value)
                        orientation = props.get("orientation", "landscape")
                        # Ensure we never propagate a single missing dimension – default as a pair
                        if not (w and h and w > 0 and h > 0):
                            cap_res = props.get("cap.res") or props.get("res")
                            if isinstance(cap_res, str):
                                w, h = self._parse_resolution_string(cap_res)
                        if not (w and h and w > 0 and h > 0):
                            if "portrait" in orientation:
                                w, h = 480, 800
                            elif orientation == "square":
                                w, h = 600, 600
                            else:
                                w, h = 800, 480
                        collected[d.display_id] = {
                            "device_id": d.hostname or d.display_id,
                            "width": w,
                            "height": h,
                            "orientation": orientation,
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
                w = display.width or 0
                h = display.height or 0
                orientation = display.orientation or "landscape"
                if not (w and h and w > 0 and h > 0):
                    if "portrait" in orientation:
                        w, h = 480, 800
                    elif orientation == "square":
                        w, h = 600, 600
                    else:
                        w, h = 800, 480
                collected[display.id] = {
                    "device_id": display.hostname or display.id,
                    "width": w,
                    "height": h,
                    "orientation": orientation,
                }
        return list(collected.values())

    @staticmethod
    def _parse_resolution_string(res_str: str | None):  # type: ignore
        if not res_str or "x" not in res_str:
            return 800, 480
        try:
            w_str, h_str = res_str.lower().split("x", 1)
            w = int(w_str)
            h = int(h_str)
            if w <= 0 or h <= 0:
                return 800, 480
            return w, h
        except ValueError:
            return 800, 480

    def _convert_image_to_url(self, image_info: dict[str, Any]) -> str | None:
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
        except (ValueError, TypeError):
            # If parsing fails (e.g., odd schemeless path), fall back to simple concatenation
            sep = '&' if ('?' in url) else '?'
            return f"{url}{sep}{param}={value}"

    # --- HTTP fetch helper ---
    def _request_channel_image_http_blocking(self, channel_id: str, payload: dict[str, Any]) -> tuple[bytes, str | None, str | None]:
        """Blocking variant: POST to the channel's /request-image endpoint and return raw bytes, content-type, and fingerprint."""
        # Self-call: use the loopback/internal base URL, NOT public_base_url —
        # hairpinning through the public LAN address times out from inside
        # bridge-networked containers (15s per channel request).
        base = settings.internal_api_base_url
        url = f"{base}/api/channels/{channel_id}/request-image"
        data = _json.dumps(payload).encode("utf-8")
        req = _urlreq.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Accept": "image/*,application/octet-stream",
        }, method="POST")
        timeout = getattr(settings, "channel_http_timeout_seconds", 15)
        try:
            with _urlreq.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                raw = resp.read()
                if not raw:
                    raise ValueError("empty_response")
                ctype = resp.headers.get("Content-Type")
                fp = resp.headers.get("X-Content-Fingerprint") or resp.headers.get("X-Image-Fingerprint")
                return raw, ctype, fp
        except _urlerr.HTTPError as he:  # rethrow with compact message
            raise RuntimeError(f"http_{he.code}") from he
        except _urlerr.URLError as ue:
            raise RuntimeError(f"url_error:{getattr(ue, 'reason', 'unknown')}") from ue

    async def _request_channel_image_http(self, channel_id: str, payload: dict[str, Any]) -> tuple[bytes, str | None, str | None]:
        """Async wrapper that runs the blocking HTTP request in a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(self._request_channel_image_http_blocking, channel_id, payload)


# Global instance
scene_refresh_service = SceneRefreshService()
