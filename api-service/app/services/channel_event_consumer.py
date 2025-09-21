"""Channel Event Consumer

Subscribes to channel_event_dispatcher and performs initial handling:
- Logs event
- (Future) Determines affected scenes using channel and triggers distribution / cache updates.

For now this is a placeholder so push pipeline is end-to-end.
"""
from __future__ import annotations

import asyncio
from typing import Set

from app.services.channel_events import channel_event_dispatcher, ChannelUpdateEvent
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChannelEventConsumerService:
    def __init__(self):
        self._subscribed: bool = False
        self._channels_bound: Set[str] = set()

    async def ensure_subscription(self):
        # For now we subscribe generically per event publish by hooking into dispatcher per channel lazily.
        if self._subscribed:
            return
        # We cannot blanket subscribe to all events without listing channels.
        # Strategy: expose method `register_channel(channel_id)` called by plugin discovery after push listener registration.
        self._subscribed = True
        logger.info("ChannelEventConsumerService initialized (awaiting channel registrations)")

    async def register_channel(self, channel_id: str):
        if channel_id in self._channels_bound:
            return

        async def _on_event(evt: ChannelUpdateEvent):  # noqa: D401
            # Placeholder handling: just log.
            logger.info(
                "[channel-event] channel=%s type=%s hash=%s playing=%s track=%s",
                evt.channel_id,
                evt.event_type,
                evt.hash,
                evt.payload.get("is_playing"),
                evt.payload.get("name")
            )
            # TODO: map channel_id -> scenes with push strategy, then request image generation / distribution

        await channel_event_dispatcher.subscribe(channel_id, _on_event)
        self._channels_bound.add(channel_id)
        logger.info("Registered consumer subscription for channel %s", channel_id)


channel_event_consumer = ChannelEventConsumerService()
