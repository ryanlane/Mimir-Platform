"""Debug MQTT utilities.

Provides a simple echo endpoint to simulate an inbound MQTT frame being
forwarded to dashboard WebSocket clients without needing a real broker
publish. This is ONLY for debugging in non-production environments.

POST /api/debug/mqtt/echo
Body (JSON):
  {
    "topic": "mimir/test/evt",          # required, must start with mimir/
    "payload": {"any": "json"},        # optional (object|string|number|array)
    "qos": 0,                           # optional
    "retain": false                     # optional
  }

Response:
  { "forwarded": true, "topic": "...", "payload": <parsed>, "note": "..." }

Safeguards:
  * Requires topic to start with mimir/
  * Disabled automatically if settings.debug is False unless explicitly enabled
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.logging import get_logger
from app.services.mqtt_ws_bridge import forward_mqtt_message, should_forward
from app.services.mqtt_debug_stats import mqtt_debug_stats

logger = get_logger(__name__)

router = APIRouter(prefix="/debug/mqtt", tags=["debug", "mqtt"])


class EchoRequest(BaseModel):
    topic: str = Field(..., description="MQTT topic (must begin with mimir/)")
    payload: Any | None = Field(None, description="Arbitrary JSON-compatible payload")
    qos: int | None = Field(None, ge=0, le=2)
    retain: bool | None = None


class EchoResponse(BaseModel):
    forwarded: bool
    topic: str
    payload: Any | None
    note: str | None = None


def _ensure_enabled():  # simple dependency gate
    if not getattr(settings, "debug", False) and not getattr(settings, "enable_debug_mqtt_echo", False):
        raise HTTPException(status_code=403, detail="Debug MQTT echo endpoint disabled")


@router.post("/echo", response_model=EchoResponse)
async def mqtt_echo(req: EchoRequest, burst: int | None = None, _: None = Depends(_ensure_enabled)):
    if not should_forward(req.topic):
        raise HTTPException(status_code=400, detail="Topic must begin with mimir/")
    if '#' in req.topic or '+' in req.topic:
        raise HTTPException(status_code=400, detail="Wildcards (#,+) not allowed in publish topics")

    # Prepare synthetic bytes payload (JSON serialization done here)
    import json
    if req.payload is None:
        raw_bytes = b"null"
    elif isinstance(req.payload, (str, int, float, bool)):
        raw_bytes = json.dumps(req.payload).encode()
    else:
        try:
            raw_bytes = json.dumps(req.payload).encode()
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Payload not JSON serializable: {e}") from e

    count = burst if (burst and burst > 0) else 1
    if count > 1000:
        raise HTTPException(status_code=400, detail="Burst too large (max 1000)")
    for i in range(count):
        # For burst >1, mutate a simple index field if payload is object
        send_bytes = raw_bytes
        if count > 1 and isinstance(req.payload, dict):
            import json as _json
            mutated = {**req.payload, "_burst_index": i}
            send_bytes = _json.dumps(mutated).encode()
        await forward_mqtt_message(
            topic=req.topic,
            payload_bytes=send_bytes,
            qos=req.qos,
            retain=req.retain,
        )

    note = f"Forwarded {count} message(s) to dashboards"
    return EchoResponse(forwarded=True, topic=req.topic, payload=req.payload, note=note)


@router.get("/stats")
async def mqtt_stats(limit: int | None = None):
        """Return current in-memory MQTT debug stats.

        Query Params:
            limit: optional, limit number of topic entries (most recent first)
        """
        snap = mqtt_debug_stats.snapshot()
        topics = snap["topics"]
        if limit is not None and limit >= 0:
                topics = topics[:limit]
        return {"total_topics": snap["total_topics"], "topics": topics}
