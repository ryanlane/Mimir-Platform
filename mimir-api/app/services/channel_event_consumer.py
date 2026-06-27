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

"""Channel Event Consumer: handles push channel update events and triggers scene refreshes (with debounce, cache, and fallback polling)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import Scene
from app.services.channel_events import ChannelUpdateEvent, channel_event_dispatcher
from app.services.now_playing_interrupt_service import now_playing_interrupt_service
from app.services.scene_refresh_service import scene_refresh_service

logger = get_logger(__name__)

_METRICS = False  # metrics disabled (optional dependency)


class ChannelEventConsumerService:
    def __init__(self) -> None:
        self._subscribed = False
        self._channels_bound: set[str] = set()
        # Base-channel cache: push scenes where this channel IS the primary content
        self._channel_scene_cache: dict[str, set[str]] = {}
        # Interrupt-source cache: {channel_id: {scene_id: {priority, resume_delay_seconds}}}
        # Covers ALL scenes (not just push scenes) since the base content may be scheduler-driven.
        self._interrupt_channel_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._cache_last_load = 0.0
        self._cache_ttl_seconds = getattr(settings, "push_channel_scene_cache_ttl", 30)
        self._scene_last_refresh: dict[str, float] = {}
        self._debounce_seconds = getattr(settings, "push_debounce_seconds", 5.0)
        self._stale_task: asyncio.Task | None = None
        self._running = False
        # Track last processed event hash per (channel_id, scene_id) so we don't re-generate
        # an identical image when only the playback progress advanced but track + play state unchanged.
        self._scene_last_hash: dict[tuple[str, str], str] = {}

    async def ensure_subscription(self) -> None:
        if self._subscribed:
            return
        self._subscribed = True
        logger.info("channel_event_consumer.started")
        if not self._running:
            self._running = True
            self._stale_task = asyncio.create_task(self._stale_check_loop())

    async def register_channel(self, channel_id: str) -> None:
        if channel_id in self._channels_bound:
            return

        async def _on_event(evt: ChannelUpdateEvent):  # noqa: D401
            logger.info(
                "channel.push evt channel=%s type=%s hash=%s", evt.channel_id, evt.event_type, evt.hash
            )
            # Ensure caches are fresh before both routing paths
            self._maybe_reload_cache()

            # ── Path 1: base-channel push (scene uses this as primary content) ──
            scenes = self._channel_scene_cache.get(evt.channel_id, set())
            now = time.monotonic()
            for scene_id in scenes:
                # Hash-based duplicate suppression (track id + play state stable)
                if evt.hash:
                    key = (evt.channel_id, scene_id)
                    prev_hash = self._scene_last_hash.get(key)
                    if prev_hash == evt.hash:
                        logger.debug(
                            "scene.refresh.skip_unchanged scene=%s channel=%s hash=%s", scene_id, evt.channel_id, evt.hash
                        )
                        continue
                    self._scene_last_hash[key] = evt.hash
                last = self._scene_last_refresh.get(scene_id, 0.0)
                if now - last < self._debounce_seconds:
                    logger.debug(
                        "scene.refresh.debounce scene=%s channel=%s delta=%.2f<%.2f", scene_id, evt.channel_id, now - last, self._debounce_seconds
                    )
                    continue
                self._scene_last_refresh[scene_id] = now
                asyncio.create_task(self._invoke_refresh(scene_id, reason="push"))

            # ── Path 2: interrupt-source push (this channel may pre-empt base content) ──
            interrupt_scenes = self._interrupt_channel_cache.get(evt.channel_id)
            if interrupt_scenes:
                logger.debug(
                    "channel.interrupt_push channel=%s interrupt_scenes=%s",
                    evt.channel_id,
                    list(interrupt_scenes.keys()),
                )
                asyncio.create_task(
                    now_playing_interrupt_service.on_push_event(evt, interrupt_scenes)
                )

        await channel_event_dispatcher.subscribe(channel_id, _on_event)
        self._channels_bound.add(channel_id)
        logger.info("channel_event_consumer.channel_registered channel=%s", channel_id)

    def _maybe_reload_cache(self) -> None:
        now = time.monotonic()
        if (now - self._cache_last_load) > self._cache_ttl_seconds:
            self._reload_cache()

    def _get_scenes_for_channel(self, channel_id: str) -> set[str]:
        self._maybe_reload_cache()
        return self._channel_scene_cache.get(channel_id, set())

    def _reload_cache(self) -> None:
        self._cache_last_load = time.monotonic()
        base_mapping: dict[str, set[str]] = {}
        interrupt_mapping: dict[str, dict[str, dict[str, Any]]] = {}

        with SessionLocal() as db:
            # Base channels: only push scenes need event-driven refreshes
            push_scenes = db.query(Scene).filter(Scene.update_strategy == "push").all()
            for s in push_scenes:
                for cfg in (s.channels or []):
                    if not isinstance(cfg, dict):
                        continue
                    cid = cfg.get("channel_id")
                    if not cid:
                        continue
                    base_mapping.setdefault(cid, set()).add(s.id)

            # Interrupt sources: all scenes (base content may be scheduler-driven)
            all_scenes = db.query(Scene).all()
            for s in all_scenes:
                for src in (s.interrupt_sources or []):
                    if not isinstance(src, dict):
                        continue
                    cid = src.get("channel_id")
                    if not cid:
                        continue
                    interrupt_mapping.setdefault(cid, {})[s.id] = {
                        "priority": src.get("priority", 10),
                        "resume_delay_seconds": src.get("resume_delay_seconds", 5.0),
                    }

        self._channel_scene_cache = base_mapping
        self._interrupt_channel_cache = interrupt_mapping
        logger.debug(
            "channel_scene_cache.reloaded base_channels=%d interrupt_channels=%d",
            len(base_mapping),
            len(interrupt_mapping),
        )

    async def _invoke_refresh(self, scene_id: str, reason: str) -> None:
        result = await scene_refresh_service.refresh_scene(
            scene_id, trigger_reason=reason, force=False
        )
        logger.info(
            "scene.refresh.result scene=%s reason=%s status=%s displays=%d skipped=%s errors=%d",
            result.scene_id,
            reason,
            result.status,
            result.displays_updated,
            result.skipped_reason,
            len(result.errors or []),
        )
        if _METRICS:  # pragma: no cover
            pass  # placeholder for metrics hook

    async def _stale_check_loop(self) -> None:
        interval = getattr(settings, "push_fallback_stale_check_interval", 30)
        while self._running:
            await asyncio.sleep(interval)
            now = time.monotonic()
            with SessionLocal() as db:
                push_scenes = db.query(Scene).filter(Scene.update_strategy == "push").all()
                for s in push_scenes:
                    threshold = getattr(s, "push_fallback_poll_seconds", None)
                    if not threshold:
                        continue
                    # Bootstrap-only fallback: once a scene has successfully displayed
                    # content (content_epoch > 0), we rely solely on push events and do not
                    # run periodic fallback refreshes anymore. This avoids polling loops for
                    # long-lived content like music tracks.
                    if (getattr(s, "content_epoch", None) or 0) > 0:
                        continue
                    last = self._scene_last_refresh.get(s.id, 0.0)
                    if last == 0.0 or (now - last) > threshold:
                        logger.debug(
                            "scene.fallback_refresh scene=%s last=%.1f age=%.1f threshold=%s",
                            s.id,
                            last,
                            now - last,
                            threshold,
                        )
                        self._scene_last_refresh[s.id] = now
                        asyncio.create_task(
                            self._invoke_refresh(s.id, reason="fallback")
                        )
        # Allow CancelledError to bubble for graceful shutdown


channel_event_consumer = ChannelEventConsumerService()
