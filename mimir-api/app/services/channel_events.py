"""Channel Event Dispatcher

Provides a lightweight in-process pub/sub system for channel push events.
Initial implementation is in-memory only. Future iterations may add Redis
or MQTT broadcast.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Optional, Awaitable

from app.core.logging import get_logger

try:  # metrics optional
    from app.core.metrics import metrics  # type: ignore
    METRICS_AVAILABLE = True
except Exception:  # pragma: no cover
    METRICS_AVAILABLE = False

logger = get_logger(__name__)


@dataclass(slots=True)
class ChannelUpdateEvent:
    channel_id: str
    event_type: str
    payload: Dict[str, Any]
    ts: float
    version: int = 1
    hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:  # convenience for serialization
        return asdict(self)


Callback = Callable[[ChannelUpdateEvent], Awaitable[None]] | Callable[[ChannelUpdateEvent], None]


class ChannelEventDispatcher:
    """In-memory dispatcher for channel update events.

    Listeners register per channel. For now we do not track per-scene subscribers;
    the distribution layer can perform scene fan-out based on channel usage.
    """

    def __init__(self):
        self._listeners: Dict[str, List[Callback]] = {}
        self._last_event: Dict[str, ChannelUpdateEvent] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel_id: str, callback: Callback) -> None:
        async with self._lock:
            lst = self._listeners.setdefault(channel_id, [])
            if callback not in lst:
                lst.append(callback)
                logger.info(f"Subscribed listener to channel {channel_id} (count={len(lst)})")
            # Optionally replay last event
            last = self._last_event.get(channel_id)
        if last:
            await self._safe_invoke(callback, last)

    async def unsubscribe(self, channel_id: str, callback: Callback) -> None:
        async with self._lock:
            lst = self._listeners.get(channel_id)
            if not lst:
                return
            if callback in lst:
                lst.remove(callback)
                logger.info(f"Unsubscribed listener from channel {channel_id} (count={len(lst)})")

    async def publish(self, event: ChannelUpdateEvent) -> None:
        # Dedupe identical events (hash based) if possible
        prev = self._last_event.get(event.channel_id)
        if prev and prev.hash and event.hash and prev.hash == event.hash:
            logger.debug(f"Duplicate event skipped for {event.channel_id} hash={event.hash}")
            if METRICS_AVAILABLE:
                metrics.distribution_error(event.channel_id, "channel_push", "duplicate")  # reuse counter
            return
        self._last_event[event.channel_id] = event

        async with self._lock:
            listeners = list(self._listeners.get(event.channel_id, []))
        if not listeners:
            logger.debug(f"Event published for {event.channel_id} with no listeners")
            return

        if METRICS_AVAILABLE:
            try:
                metrics.distribution_content_assigned(event.channel_id, "push", event.hash or "")
            except Exception:  # pragma: no cover
                pass

        logger.debug(f"Dispatching event for {event.channel_id} to {len(listeners)} listener(s)")
        await asyncio.gather(*(self._safe_invoke(cb, event) for cb in listeners), return_exceptions=True)

    async def get_last_event(self, channel_id: str) -> Optional[ChannelUpdateEvent]:
        return self._last_event.get(channel_id)

    async def _safe_invoke(self, callback: Callback, event: ChannelUpdateEvent) -> None:
        try:
            res = callback(event)
            if asyncio.iscoroutine(res):  # type: ignore
                await res  # type: ignore
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Channel event listener raised: {exc}")


# Global dispatcher instance
channel_event_dispatcher = ChannelEventDispatcher()
