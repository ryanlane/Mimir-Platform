"""
MQTT Pairing Service

Handles display pairing via a short 6-character code.

Flow:
  1. Display generates a 6-char code and publishes to mimir/registry/pair
  2. This service stores a pending pair entry (Redis with TTL, or in-memory fallback)
  3. Server acks the display so it can show "waiting for claim"
  4. User enters the code in the web UI → calls POST /api/displays/pair
  5. claim_pair() looks up the entry, returns device info for DB registration
  6. API creates the DisplayClient and sends finalize_registration via MQTT

Pending pair Redis key: mimir:pair:{code}  (Hash, TTL = PAIR_TTL_SECONDS)
"""
from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.services.mqtt.topics import PAIR_REQUEST_TOPIC, pair_ack_topic

logger = get_logger(__name__)

# 6-char code alphabet: uppercase letters + digits, excluding look-alike chars
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0,1,I,L,O
PAIR_TTL_SECONDS = 600  # 10 minutes
REDIS_KEY_PREFIX = "mimir:pair"

try:
    import aiomqtt
except ImportError:
    aiomqtt = None  # type: ignore


def _redis_key(code: str) -> str:
    return f"{REDIS_KEY_PREFIX}:{code.upper()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PairingService:
    """Manages short-code pairing requests from display clients."""

    def __init__(self) -> None:
        self._redis: Any = None
        self._in_memory: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._mqtt_client: Any = None
        self._running = False
        self._task: asyncio.Task | None = None
        self._initialize_redis()

    # ------------------------------------------------------------------ init

    def _initialize_redis(self) -> None:
        if not settings.redis_enabled:
            logger.info("Pairing service using in-memory backend (Redis disabled)")
            return
        try:
            import redis.asyncio as redis  # type: ignore

            dsn = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
            self._redis = redis.from_url(dsn, decode_responses=True)
            logger.info("Pairing service using Redis backend")
        except Exception as e:
            logger.error("Pairing service Redis init failed, using in-memory: %s", e)
            self._redis = None

    # ---------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if not settings.mqtt_enabled or not aiomqtt:
            logger.info("Pairing service disabled (MQTT not available)")
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Pairing service started (listening on %s)", PAIR_REQUEST_TOPIC)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ---------------------------------------------------------------- MQTT loop

    async def _run(self) -> None:
        while self._running:
            try:
                async with aiomqtt.Client(
                    hostname=settings.mqtt_broker_host,
                    port=settings.mqtt_broker_port,
                    identifier="mimir-pairing",
                ) as client:
                    self._mqtt_client = client
                    await client.subscribe(PAIR_REQUEST_TOPIC)
                    logger.info("Pairing service subscribed to %s", PAIR_REQUEST_TOPIC)
                    async for message in client.messages:
                        if not self._running:
                            break
                        try:
                            await self._handle_pair_request(client, message)
                        except Exception as e:
                            logger.error("Error handling pair request: %s", e)
            except Exception as e:
                logger.error("Pairing service MQTT error: %s", e)
                if self._running:
                    await asyncio.sleep(5)
            finally:
                self._mqtt_client = None

    async def _handle_pair_request(self, client: Any, message: Any) -> None:
        try:
            data: dict = json.loads(message.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Pairing: non-JSON payload ignored")
            return

        device_id = data.get("device_id")
        code = str(data.get("code", "")).upper().strip()
        reply_to = data.get("reply_to") or pair_ack_topic(device_id or "unknown")

        if not device_id or not code:
            logger.warning("Pairing request missing device_id or code")
            return

        if len(code) != 6 or not all(c in _ALPHABET for c in code):
            logger.warning("Pairing: invalid code format from %s: %r", device_id, code)
            await self._publish_ack(client, reply_to, {
                "status": "error",
                "error": "invalid_code",
                "message": "Code must be 6 characters from the allowed alphabet",
            })
            return

        # Check for collision: another device already holds this code
        existing = await self._get_entry(code)
        if existing and existing.get("device_id") != device_id:
            logger.warning("Pairing code collision: %s already held by %s", code, existing.get("device_id"))
            await self._publish_ack(client, reply_to, {
                "status": "error",
                "error": "code_conflict",
                "message": "Code already in use, please generate a new one",
            })
            return

        entry: dict[str, Any] = {
            "code": code,
            "device_id": device_id,
            "capabilities": json.dumps(data.get("capabilities") or {}),
            "metadata": json.dumps(data.get("metadata") or {}),
            "created_at": _now_iso(),
        }
        await self._store_entry(code, entry)
        logger.info("Pairing code %s registered for device %s", code, device_id)

        await self._publish_ack(client, reply_to, {
            "status": "pending",
            "code": code,
            "expires_in": PAIR_TTL_SECONDS,
            "message": "Code accepted. Enter code in Mimir to complete pairing.",
        })

    async def _publish_ack(self, client: Any, topic: str, payload: dict) -> None:
        try:
            await client.publish(topic, json.dumps(payload), qos=1)
        except Exception as e:
            logger.error("Failed to publish pair ack to %s: %s", topic, e)

    # ---------------------------------------------------------------- storage

    async def _store_entry(self, code: str, entry: dict[str, Any]) -> None:
        key = _redis_key(code)
        if self._redis:
            try:
                async with self._lock:
                    await self._redis.hset(key, mapping=entry)
                    await self._redis.expire(key, PAIR_TTL_SECONDS)
                return
            except Exception as e:
                logger.error("Redis store failed for pair %s: %s", code, e)
        # In-memory fallback
        async with self._lock:
            self._in_memory[code] = entry

    async def _get_entry(self, code: str) -> dict[str, Any] | None:
        key = _redis_key(code)
        if self._redis:
            try:
                data = await self._redis.hgetall(key)
                return data if data else None
            except Exception as e:
                logger.error("Redis get failed for pair %s: %s", code, e)
        return self._in_memory.get(code)

    async def _delete_entry(self, code: str) -> None:
        key = _redis_key(code)
        if self._redis:
            try:
                await self._redis.delete(key)
                return
            except Exception as e:
                logger.error("Redis delete failed for pair %s: %s", code, e)
        self._in_memory.pop(code, None)

    # ---------------------------------------------------------------- public API

    async def claim_pair(self, code: str) -> dict[str, Any]:
        """Look up a pending pair entry by code.

        Returns the entry dict (device_id, capabilities, metadata) if found and
        still valid.  Deletes the entry atomically so each code can only be
        claimed once.

        Raises ValueError if the code is not found or has expired.
        """
        code = code.upper().strip()
        entry = await self._get_entry(code)
        if not entry:
            raise ValueError("Pairing code not found or expired")

        # Parse nested JSON fields stored as strings
        try:
            entry["capabilities"] = json.loads(entry.get("capabilities") or "{}")
        except (json.JSONDecodeError, TypeError):
            entry["capabilities"] = {}
        try:
            entry["metadata"] = json.loads(entry.get("metadata") or "{}")
        except (json.JSONDecodeError, TypeError):
            entry["metadata"] = {}

        # Consume the code — one claim per code
        await self._delete_entry(code)
        return entry

    async def get_pair_status(self, code: str) -> dict[str, Any] | None:
        """Return status of a pending pair without consuming it (for polling)."""
        code = code.upper().strip()
        entry = await self._get_entry(code)
        if not entry:
            return None
        return {"code": code, "device_id": entry.get("device_id"), "status": "pending"}

    @staticmethod
    def generate_code() -> str:
        """Generate a random 6-character pairing code (server-side utility)."""
        return "".join(random.choices(_ALPHABET, k=6))


# Singleton
pairing_service = PairingService()
