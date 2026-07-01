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

"""Hybrid Redis-backed MQTT discovery registry.

Stores ephemeral device discovery state derived from enriched heartbeat frames.
Falls back to in-memory dict if Redis unavailable or disabled.

States:
- discovered: heartbeat seen, minimal info
- pre_registered: capabilities captured, awaiting manual approval
- registered: linked to DisplayClient (mirrors DB)
- offline: stale beyond offline grace, not yet expired

Redis Hash Keys: mimir:disc:<device_id>
Hash Fields:
  device_id, state, first_seen, last_seen, last_heartbeat,
  capabilities (json), meta (json), display_id, hardware_fingerprint,
  conflict (0|1), offline_since

TTL Strategy:
  Set/refresh TTL only for states that may expire (discovered, pre_registered, offline).
  Registered devices rely on DB for persistence (no TTL => keep hash or delete after promotion).

Public API intentionally minimal for first phase.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ISO = lambda dt: dt.astimezone(timezone.utc).isoformat()  # noqa: E731

REDIS_KEY_PREFIX = "mimir:disc"

class DiscoveryRegistry:
    def __init__(self):
        self._redis = None
        self._in_memory: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._ws_last_emit: dict[str, float] = {}
        self._ws_debounce = settings.mqtt_discovery_ws_debounce_seconds
        self._offline_grace = settings.mqtt_discovery_offline_grace_seconds
        self._expiry_discovered = settings.mqtt_discovery_expiry_seconds
        self._expiry_prereg = settings.mqtt_discovery_preregistered_expiry_seconds
        self._sweeper_task: asyncio.Task | None = None
        self._initialize_redis()
    # Field names added for finalize flow
    # registration_key: str (opaque key issued by API)
    # finalize_ack_ts: ISO timestamp when device acknowledged finalize

    # -------- Initialization --------
    def _initialize_redis(self):
        if not settings.redis_enabled:
            logger.info("Discovery registry using in-memory backend (Redis disabled)")
            return
        try:
            # Lazy import; project uses a custom redis_manager that may not yet exist
            try:
                from redis_manager import get_redis_manager, init_redis
                init_redis()
                self._redis = get_redis_manager()
                logger.info("Discovery registry using redis_manager backend")
            except ImportError:
                # Fallback to direct redis library if installed
                import redis.asyncio as redis
                dsn = settings.redis_dsn or f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
                self._redis = redis.from_url(dsn, decode_responses=True)
                logger.info("Discovery registry using direct redis client")
        except Exception as e:  # pragma: no cover
            # Broad except acceptable here to fall back gracefully to in-memory registry.
            logger.error("Failed to initialize Redis for discovery registry: %s", e)
            self._redis = None

    # -------- Public Lifecycle --------
    async def start(self):
        if self._sweeper_task is None:
            self._sweeper_task = asyncio.create_task(self._sweeper_loop(), name="mqtt-disc-sweeper")

    async def stop(self):
        if self._sweeper_task:
            self._sweeper_task.cancel()
            try:
                await self._sweeper_task
            except asyncio.CancelledError:
                pass
            self._sweeper_task = None

    # -------- Core Operations --------
    async def upsert_from_heartbeat(self, device_id: str, payload: dict) -> dict:
        now = datetime.now(timezone.utc)
        capabilities = self._extract_capabilities(payload)
        registration_state = payload.get("registration_state")
        display_id = payload.get("display_id") if registration_state == "finalized" else None
        hardware_fp = payload.get("hardware_fingerprint")

        async with self._lock:
            existing = await self._get(device_id)
            first_seen = existing.get("first_seen") if existing else ISO(now)
            state = existing.get("state") if existing else "discovered"

            # State upgrades
            if state == "discovered" and capabilities:
                state = "pre_registered"
            if registration_state == "finalized" and display_id:
                state = "registered"
            # If existing registered, never downgrade
            if existing and existing.get("state") == "registered":
                state = "registered"

            record = {
                "device_id": device_id,
                "state": state,
                "first_seen": first_seen,
                "last_seen": ISO(now),
                "last_heartbeat": ISO(now),
                "capabilities": json.dumps(capabilities) if capabilities else None,
                "meta": json.dumps({k: v for k, v in payload.items() if k not in ("cap", "capabilities")}),
                "display_id": display_id or (existing.get("display_id") if existing else None),
                "hardware_fingerprint": hardware_fp or (existing.get("hardware_fingerprint") if existing else None),
                "conflict": existing.get("conflict", 0) if existing else 0,
                "offline_since": None,
                "registration_key": existing.get("registration_key") if existing else None,
                "finalize_ack_ts": existing.get("finalize_ack_ts") if existing else None,
            }

            # Conflict detection: different hardware fingerprint
            if existing and existing.get("hardware_fingerprint") and hardware_fp and existing.get("hardware_fingerprint") != hardware_fp:
                record["conflict"] = 1
                logger.warning("Discovery conflict device_id=%s previous_fp=%s new_fp=%s", device_id, existing.get("hardware_fingerprint"), hardware_fp)

            await self._persist(record)
            return record

    async def promote_to_registered(self, device_id: str, display_id: str) -> bool:
        async with self._lock:
            existing = await self._get(device_id)
            if not existing:
                return False
            existing.update({
                "state": "registered",
                "display_id": display_id,
                "offline_since": None,
            })
            await self._persist(existing)
            return True

    async def set_registration_key(self, device_id: str, registration_key: str) -> bool:
        async with self._lock:
            rec = await self._get(device_id)
            if not rec:
                return False
            rec["registration_key"] = registration_key
            await self._persist(rec)
            return True

    async def acknowledge_finalize(self, device_id: str) -> bool:
        now = datetime.now(timezone.utc)
        async with self._lock:
            rec = await self._get(device_id)
            if not rec:
                return False
            rec["finalize_ack_ts"] = ISO(now)
            # If not already registered (e.g., device persisted key across restart), mark registered
            if rec.get("display_id") and rec.get("state") != "registered":
                rec["state"] = "registered"
            await self._persist(rec)
            return True

    async def mark_offline_if_stale(self):
        now = datetime.now(timezone.utc)
        devices = await self.list_devices()
        changed = []
        for rec in devices:
            if rec["state"] in ("registered", "offline"):
                last_hb = rec.get("last_heartbeat")
                if not last_hb:
                    continue
                try:
                    hb_dt = datetime.fromisoformat(last_hb)
                except ValueError:
                    # Malformed timestamp; skip
                    continue
                delta = (now - hb_dt).total_seconds()
                if rec["state"] != "offline" and delta > self._offline_grace:
                    rec["offline_since"] = ISO(now)
                    rec["state"] = "offline"
                    await self._persist(rec)
                    changed.append(rec)
                elif rec["state"] == "offline" and delta <= self._offline_grace:
                    # Come back online -> revert to prior active state (infer from capabilities)
                    rec["offline_since"] = None
                    if rec.get("display_id"):
                        rec["state"] = "registered"
                    elif rec.get("capabilities"):
                        rec["state"] = "pre_registered"
                    else:
                        rec["state"] = "discovered"
                    await self._persist(rec)
                    changed.append(rec)
        return changed

    async def sweep_expired(self):
        now = datetime.now(timezone.utc)
        devices = await self.list_devices()
        expired = []
        for rec in devices:
            if rec["state"] == "registered":
                continue
            last_seen = rec.get("last_seen")
            if not last_seen:
                continue
            try:
                ls_dt = datetime.fromisoformat(last_seen)
            except ValueError:
                continue
            age = (now - ls_dt).total_seconds()
            if rec["state"] == "discovered" and age > self._expiry_discovered:
                await self._delete(rec["device_id"])
                expired.append(rec)
            elif rec["state"] in ("pre_registered", "offline") and age > self._expiry_prereg:
                await self._delete(rec["device_id"])
                expired.append(rec)
        return expired

    async def list_devices(self, states: list[str] | None = None) -> list[dict]:
        if self._redis:
            # SCAN all keys (small cardinality expected)
            cursor = 0
            keys: list[str] = []
            while True:
                cursor, batch = await self._redis.scan(cursor=cursor, match=f"{REDIS_KEY_PREFIX}:*")
                keys.extend(batch)
                if cursor == 0:
                    break
                if len(keys) > 5000:  # safety cutoff
                    break
            results = []
            for k in keys:
                h = await self._redis.hgetall(k)
                if not h:
                    continue
                rec = self._hydrate(h)
                if states and rec["state"] not in states:
                    continue
                results.append(rec)
            return results
        # In-memory path
        out = []
        for rec in self._in_memory.values():
            if states and rec["state"] not in states:
                continue
            out.append(rec.copy())
        return out

    async def get(self, device_id: str) -> dict | None:
        return await self._get(device_id)

    # -------- Internal Helpers --------
    async def _get(self, device_id: str) -> dict | None:
        if self._redis:
            h = await self._redis.hgetall(f"{REDIS_KEY_PREFIX}:{device_id}")
            if not h:
                return None
            return self._hydrate(h)
        rec = self._in_memory.get(device_id)
        return rec.copy() if rec else None

    async def _persist(self, record: dict):
        if self._redis:
            key = f"{REDIS_KEY_PREFIX}:{record['device_id']}"
            flat: dict[str, str] = {}
            for k, v in record.items():
                if v is None:
                    continue
                flat[k] = v if isinstance(v, str) else json.dumps(v) if not isinstance(v, (int, float)) else str(v)
            await self._redis.hset(key, mapping=flat)
            # TTL logic
            if record["state"] in ("discovered", "pre_registered", "offline"):
                ttl = self._expiry_discovered if record["state"] == "discovered" else self._expiry_prereg
                try:
                    await self._redis.expire(key, ttl)
                except Exception:  # pragma: no cover
                    # Ignore TTL failures (non-critical)
                    pass
        else:
            self._in_memory[record["device_id"]] = record.copy()

    async def _delete(self, device_id: str):
        if self._redis:
            try:
                await self._redis.delete(f"{REDIS_KEY_PREFIX}:{device_id}")
            except Exception:  # pragma: no cover - defensive delete
                pass
        else:
            self._in_memory.pop(device_id, None)

    def _hydrate(self, h: dict) -> dict:
        rec = dict(h)
        # Attempt JSON decode for capabilities/meta
        if isinstance(rec.get("capabilities"), str):
            try:
                rec["capabilities"] = json.loads(rec["capabilities"])
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(rec.get("meta"), str):
            try:
                rec["meta"] = json.loads(rec["meta"])
            except (json.JSONDecodeError, TypeError):
                pass
        return rec

    def _extract_capabilities(self, payload: dict) -> dict | None:
        # Accept cap shorthand or full capabilities field
        caps = payload.get("cap") or payload.get("capabilities")
        if not caps or not isinstance(caps, dict):
            return None
        # Normalize keys
        norm = {}
        if "res" in caps and isinstance(caps["res"], (list, tuple)):
            norm["resolution"] = caps["res"]
        if "ori" in caps:
            norm["orientation"] = caps["ori"]
        for k in ("redis_distribution", "content_claiming", "client_version"):
            if k in caps:
                norm[k] = caps[k]
        # Add any other simple scalar fields
        for k, v in caps.items():
            if k not in norm and isinstance(v, (str, int, float, bool)):
                norm[k] = v
        return norm

    async def _sweeper_loop(self):  # pragma: no cover - timing based
        while True:
            try:
                changed = await self.mark_offline_if_stale()
                expired = await self.sweep_expired()
                if changed or expired:
                    logger.info("Discovery sweeper: changed=%d expired=%d", len(changed), len(expired))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Discovery sweeper error: %s", e)
            await asyncio.sleep(30)

    # -------- Public Admin Helpers --------
    async def delete(self, device_id: str) -> bool:
        """Public deletion helper for API routes/tests.

        Parameters
        ----------
        device_id: str
            The transient device identifier to remove from the registry.

        Returns
        -------
        bool
            True if a record existed (best-effort for Redis path), False otherwise.
        """
        existing = await self._get(device_id)
        await self._delete(device_id)
        return existing is not None

# Global instance
mqtt_discovery_registry = DiscoveryRegistry()
