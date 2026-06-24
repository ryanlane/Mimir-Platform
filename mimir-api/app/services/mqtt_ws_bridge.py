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

"""MQTT -> WebSocket bridge utilities.

This module exposes a helper to forward MQTT messages (limited to the
mimir/ topic namespace) to connected WebSocket dashboard clients using the
unified `websocket_manager`.

At present the API service does not itself host a long-lived MQTT
subscription loop inside the `app` package; external scripts (e.g.
`mqtt_monitor.py`, `mqtt_presence_client.py`) operate out-of-process.
If/when an in-process subscriber is introduced, its callback should call
`forward_mqtt_message` with the raw MQTT frame data.

Event envelope emitted:
  event: "mqtt_message"
  data: {
      topic: str,
      payload: object | str,   # JSON decoded if possible else raw text
      raw_payload: str,        # Always present original text
      qos: int | None,
      retain: bool | None,
  }
"""
from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.services.websocket_manager import websocket_manager

logger = get_logger(__name__)

ALLOWED_PREFIX = "mimir/"


def _try_parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001 - lenient parse failure acceptable
        return raw


def should_forward(topic: str) -> bool:
    """Return True if the topic is within the allowed namespace.

    Adjust here if you later add dynamic subscriptions or allowlist logic.
    """
    return topic.startswith(ALLOWED_PREFIX)


async def forward_mqtt_message(
    *,
    topic: str,
    payload_bytes: bytes,
    qos: int | None = None,
    retain: bool | None = None,
) -> None:
    """Forward one MQTT publication to WebSocket dashboards.

    Parameters
    ----------
    topic: str
        Full MQTT topic.
    payload_bytes: bytes
        Raw MQTT payload bytes.
    qos: Optional[int]
        QoS level if provided by the client library.
    retain: Optional[bool]
        Retain flag if provided.
    """
    if not should_forward(topic):
        return

    raw_text = ""
    try:
        raw_text = payload_bytes.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover - extremely unlikely
        raw_text = "<decode-error>"

    parsed = _try_parse_json(raw_text)

    # Emit via unified event envelope; dashboards already filter on event name.
    try:
        # Unified manager uses `audience` kw instead of legacy dashboards_only flag.
        await websocket_manager.emit_event(
            "mqtt_message",
            {
                "topic": topic,
                "payload": parsed,
                "raw_payload": raw_text,
                "qos": qos,
                "retain": retain,
            },
            audience="dashboards",
        )
        logger.debug(
            "Forwarded MQTT message topic=%s len=%d parsed_type=%s", topic, len(raw_text), type(parsed).__name__
        )
    except TypeError as te:  # signature mismatch safeguard
        logger.error(
            "WebSocket emit_event signature mismatch when forwarding MQTT (topic=%s): %s", topic, te
        )
    except Exception as e:  # pragma: no cover - defensive catch
        logger.error("Unexpected error emitting mqtt_message event: %s", e, exc_info=True)


__all__ = ["forward_mqtt_message", "should_forward"]
