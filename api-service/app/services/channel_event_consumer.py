"""Channel Event Consumer: handles push channel update events and triggers scene refreshes (with debounce, cache, and fallback polling)."""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Set

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import Scene
from app.services.channel_events import ChannelUpdateEvent, channel_event_dispatcher
from app.services.scene_refresh_service import scene_refresh_service

logger = get_logger(__name__)

_METRICS = False  # metrics disabled (optional dependency)


class ChannelEventConsumerService:
    def __init__(self) -> None:
        self._subscribed = False
        self._channels_bound: Set[str] = set()
        self._channel_scene_cache: Dict[str, Set[str]] = {}
        self._cache_last_load = 0.0
        self._cache_ttl_seconds = getattr(settings, "push_channel_scene_cache_ttl", 30)
        self._scene_last_refresh: Dict[str, float] = {}
        self._debounce_seconds = getattr(settings, "push_debounce_seconds", 5.0)
        self._stale_task: asyncio.Task | None = None
        self._running = False
        # Track last processed event hash per (channel_id, scene_id) so we don't re-generate
        # an identical image when only the playback progress advanced but track + play state unchanged.
        self._scene_last_hash: Dict[tuple[str, str], str] = {}

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
            scenes = self._get_scenes_for_channel(evt.channel_id)
            if not scenes:
                logger.debug("channel.push.no_scenes channel=%s", evt.channel_id)
                return
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

        await channel_event_dispatcher.subscribe(channel_id, _on_event)
        self._channels_bound.add(channel_id)
        logger.info("channel_event_consumer.channel_registered channel=%s", channel_id)

    def _get_scenes_for_channel(self, channel_id: str) -> Set[str]:
        now = time.monotonic()
        if (now - self._cache_last_load) > self._cache_ttl_seconds:
            self._reload_cache()
        return self._channel_scene_cache.get(channel_id, set())

    def _reload_cache(self) -> None:
        self._cache_last_load = time.monotonic()
        mapping: Dict[str, Set[str]] = {}
        with SessionLocal() as db:
            scenes = db.query(Scene).filter(Scene.update_strategy == "push").all()
            for s in scenes:
                for cfg in (s.channels or []):
                    if not isinstance(cfg, dict):
                        continue
                    cid = cfg.get("channel_id")
                    if not cid:
                        continue
                    mapping.setdefault(cid, set()).add(s.id)
        self._channel_scene_cache = mapping
        logger.debug("channel_scene_cache.reloaded channels=%d", len(mapping))

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
