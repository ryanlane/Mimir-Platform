"""Fleet OTA rollout controller (Phase 3).

Publishes the desired display-client version as a retained MQTT message and
manages canary-first promotion:

    mimir/fleet/desired_version (retained)
    {
        "version": "1.0.4",
        "artifact": "mimir_display-1.0.4.tar.gz",
        "sha256": "...",
        "download_path": "/api/client-releases/v1.0.4/download",
        "min_server_version": "0.0.0",
        "phase": "canary" | "all",
        "ts": "<iso8601>"
    }

Phase semantics (evaluated client-side):
    - "canary": only displays whose tags include 'canary' update
    - "all":    every display updates

Promotion logic (stateless, recomputed every cycle — no persistence needed):
    - No online canary displays  -> publish phase "all" immediately.
    - Online canaries exist      -> publish "canary"; once ALL online canaries
      report client_version == desired continuously for PROMOTE_AFTER seconds,
      switch to "all".
    - Canary stuck/failed        -> promotion never happens; fleet stays on the
      old version (fail-safe), visible in the UI via update_status.

The desired version is read from the local client-release cache manifest
(populated by mimir-update.sh), so the server only ever advertises an artifact
it can actually serve.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
PROMOTE_AFTER_SECONDS = 15 * 60
FLEET_TOPIC = "mimir/fleet/desired_version"


class FleetRolloutService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        # version -> monotonic ts when all online canaries first looked healthy
        self._canary_healthy_since: float | None = None
        self._last_published: tuple[str, str] | None = None  # (version, phase)

    # ---------- lifecycle ----------
    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="fleet_rollout_loop")
        logger.info("Fleet rollout controller started (topic=%s)", FLEET_TOPIC)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # ---------- internals ----------
    def _load_latest_manifest(self) -> dict | None:
        base = Path(getattr(settings, "client_releases_dir", "/var/opt/mimir/mimir-api/client-releases"))
        latest = base / "latest"
        manifest_path = latest / "manifest.json"
        if not manifest_path.is_file():
            return None
        try:
            return json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("fleet_rollout: invalid latest manifest: %s", exc)
            return None

    def _fleet_snapshot(self):
        """Return (online_canaries, online_all) as lists of (device_id, client_version)."""
        try:
            from app.services.mdns_discovery import mdns_discovery_service
            displays = list(mdns_discovery_service.discovered_displays.values())
        except Exception:  # pragma: no cover - service unavailable in some test setups
            return [], []
        canaries, everyone = [], []
        for d in displays:
            if not getattr(d, "is_online", False):
                continue
            props = getattr(d, "properties", None) or {}
            entry = (d.display_id, getattr(d, "client_version", None))
            everyone.append(entry)
            if str(props.get("canary", "")).lower() == "true":
                canaries.append(entry)
        return canaries, everyone

    def _decide_phase(self, desired_version: str) -> str:
        canaries, _ = self._fleet_snapshot()
        if not canaries:
            # No canary displays online — nothing to gate on.
            self._canary_healthy_since = None
            return "all"

        all_converged = all(
            (v or "").lstrip("v") == desired_version.lstrip("v") for _, v in canaries
        )
        now = time.monotonic()
        if not all_converged:
            self._canary_healthy_since = None
            return "canary"
        if self._canary_healthy_since is None:
            self._canary_healthy_since = now
            logger.info(
                "fleet_rollout: all %d online canaries on %s — promotion in %ds",
                len(canaries), desired_version, PROMOTE_AFTER_SECONDS,
            )
        if now - self._canary_healthy_since >= PROMOTE_AFTER_SECONDS:
            return "all"
        return "canary"

    async def _publish(self, manifest: dict, phase: str) -> None:
        version = str(manifest.get("version", "")).lstrip("v")
        key = (version, phase)
        if key == self._last_published:
            return
        payload = {
            "version": version,
            "artifact": manifest.get("artifact"),
            "sha256": manifest.get("sha256"),
            "download_path": f"/api/client-releases/v{version}/download",
            "min_server_version": manifest.get("min_server_version", "0.0.0"),
            "phase": phase,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        try:
            from app.services.mqtt.publisher import MQTTSceneAssignmentPublisher
            publisher = MQTTSceneAssignmentPublisher.get()
            ok = await publisher.publish_topic(FLEET_TOPIC, payload, qos=1, retain=True)
            if ok:
                self._last_published = key
                logger.info("fleet_rollout: published desired_version=%s phase=%s (retained)", version, phase)
        except Exception as exc:
            logger.warning("fleet_rollout: publish failed: %s", exc)

    async def _loop(self) -> None:
        while True:
            try:
                manifest = self._load_latest_manifest()
                if manifest and manifest.get("version"):
                    version = str(manifest["version"])
                    # New version resets the canary clock
                    if self._last_published and self._last_published[0] != version.lstrip("v"):
                        self._canary_healthy_since = None
                    phase = self._decide_phase(version)
                    await self._publish(manifest, phase)
            except Exception as exc:  # pragma: no cover - loop resilience
                logger.warning("fleet_rollout: cycle error: %s", exc)
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)


fleet_rollout_service = FleetRolloutService()
