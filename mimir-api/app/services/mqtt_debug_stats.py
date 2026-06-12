"""In-memory MQTT debug statistics.

Lightweight module to track counts and last-seen timestamps/payloads for
(mimir/*) topics received and forwarded to dashboards. Intended strictly
for short-lived debugging; no persistence or pruning beyond a max topics
cap.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

_MAX_TOPICS = 1000

@dataclass
class TopicStat:
    topic: str
    received_count: int = 0
    forwarded_count: int = 0
    last_received_ts: float | None = None
    last_forwarded_ts: float | None = None
    last_payload_preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "received_count": self.received_count,
            "forwarded_count": self.forwarded_count,
            "last_received_ts": self.last_received_ts,
            "last_forwarded_ts": self.last_forwarded_ts,
            "last_payload_preview": self.last_payload_preview,
        }

class MqttDebugStats:
    def __init__(self):
        self._topics: dict[str, TopicStat] = {}

    def record_received(self, topic: str, payload_bytes: bytes):
        stat = self._topics.get(topic)
        if stat is None:
            if len(self._topics) >= _MAX_TOPICS:
                # naive pruning: drop oldest by last_received_ts
                oldest = sorted(self._topics.values(), key=lambda s: s.last_received_ts or 0)[:10]
                for o in oldest:
                    self._topics.pop(o.topic, None)
            stat = TopicStat(topic=topic)
            self._topics[topic] = stat
        stat.received_count += 1
        stat.last_received_ts = time.time()
        stat.last_payload_preview = self._preview(payload_bytes)

    def record_forwarded(self, topic: str, payload_bytes: bytes):
        stat = self._topics.get(topic)
        if stat is None:
            self.record_received(topic, payload_bytes)
            stat = self._topics[topic]
        stat.forwarded_count += 1
        stat.last_forwarded_ts = time.time()

    def snapshot(self) -> dict[str, Any]:
        return {
            "total_topics": len(self._topics),
            "topics": [s.to_dict() for s in sorted(self._topics.values(), key=lambda s: s.last_received_ts or 0, reverse=True)],
        }

    @staticmethod
    def _preview(data: bytes, limit: int = 120) -> str:
        try:
            txt = data.decode("utf-8", errors="replace")
        except Exception:
            return "<decode-error>"
        if len(txt) > limit:
            return txt[: limit - 1] + "…"
        return txt

mqtt_debug_stats = MqttDebugStats()

__all__ = ["mqtt_debug_stats"]
