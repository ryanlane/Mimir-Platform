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

"""Now Playing Interrupt Service

Manages dynamic channel pre-emption for scenes with interrupt_sources configured.

When a push channel (e.g. Last.fm, Spotify) reports is_playing=true, this service:
  1. Updates the per-scene interrupt state for that channel
  2. Resolves the priority stack for each affected scene
  3. Triggers a scene refresh using the interrupt channel if the active source changed
  4. When is_playing goes false, schedules a resume-delay timer before reverting
     to base content (timer is cancelled if another is_playing=true event arrives
     during the wait, avoiding flicker between consecutive tracks)

Now-playing channel contract
----------------------------
Any channel that acts as an interrupt source must:
  - Declare ``supports_now_playing: True`` in its get_manifest() response
  - Include ``is_playing: bool`` at the TOP LEVEL of the push event payload

Legacy layout (``payload.track.is_playing``) is also supported as a fallback
during the Phase 2→3 transition, but new channels should use the top-level field.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.channel_events import ChannelUpdateEvent

logger = logging.getLogger(__name__)


def _extract_is_playing(payload: dict[str, Any] | None) -> bool | None:
    """Extract is_playing from a push event payload.

    Checks top-level first (standard contract), then falls back to
    ``payload["track"]["is_playing"]`` for channels not yet updated to Phase 3.
    Returns None if payload is absent or the field cannot be found.
    """
    if not isinstance(payload, dict):
        return None
    if "is_playing" in payload:
        return bool(payload["is_playing"])
    track = payload.get("track") or {}
    if "is_playing" in track:
        return bool(track["is_playing"])
    return None


class NowPlayingInterruptService:
    """In-memory priority-stack state machine for now-playing channel pre-emption.

    Per-scene state structure::

        _scene_state[scene_id][channel_id] = {
            "is_playing":  bool,
            "priority":    int,   # from interrupt_sources config
            "resume_delay": float,
            "last_ts":     float, # push event timestamp, used to break priority ties
        }

    The currently displayed source per scene is tracked in ``_active_interrupt``
    (None = base content, a channel_id string = that interrupt is on screen).
    """

    def __init__(self) -> None:
        # {scene_id: {channel_id: state_dict}}
        self._scene_state: dict[str, dict[str, dict[str, Any]]] = {}
        # {scene_id: channel_id | None}
        self._active_interrupt: dict[str, str | None] = {}
        # {scene_id: asyncio.Task} — pending resume-to-base timers
        self._resume_tasks: dict[str, asyncio.Task] = {}
        # Strong references to fire-and-forget background tasks, so they aren't
        # garbage-collected mid-execution (asyncio only holds a weak ref).
        self._background_tasks: set[asyncio.Task] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    async def on_push_event(
        self,
        evt: ChannelUpdateEvent,
        scene_interrupt_info: dict[str, dict[str, Any]],
    ) -> None:
        """Process a push event from a now-playing channel.

        Args:
            evt: The push event from the channel.
            scene_interrupt_info: Mapping of ``scene_id → {priority, resume_delay_seconds}``
                for all scenes that have this channel configured as an interrupt source.
        """
        is_playing = _extract_is_playing(evt.payload)
        if is_playing is None:
            logger.debug(
                "interrupt.no_is_playing channel=%s payload_keys=%s",
                evt.channel_id,
                list(evt.payload.keys()),
            )
            return

        logger.info(
            "interrupt.push channel=%s is_playing=%s scenes=%s",
            evt.channel_id,
            is_playing,
            list(scene_interrupt_info.keys()),
        )

        for scene_id, cfg in scene_interrupt_info.items():
            priority = int(cfg.get("priority", 10))
            resume_delay = float(cfg.get("resume_delay_seconds", 5.0))

            scene = self._scene_state.setdefault(scene_id, {})
            scene[evt.channel_id] = {
                "is_playing":   is_playing,
                "priority":     priority,
                "resume_delay": resume_delay,
                "last_ts":      evt.ts,
            }

            if is_playing:
                self._cancel_resume(scene_id)

            await self._resolve_and_trigger(scene_id, evt.channel_id, is_playing, resume_delay)

    def clear_scene(self, scene_id: str) -> None:
        """Remove all interrupt state for a scene (call on scene delete/update)."""
        self._scene_state.pop(scene_id, None)
        self._active_interrupt.pop(scene_id, None)
        self._cancel_resume(scene_id)

    def get_state(self, scene_id: str) -> dict[str, Any]:
        """Return a snapshot of interrupt state for a scene (for status endpoints)."""
        return {
            "active_interrupt": self._active_interrupt.get(scene_id),
            "sources": {
                ch: {k: v for k, v in info.items() if k != "resume_delay"}
                for ch, info in self._scene_state.get(scene_id, {}).items()
            },
        }

    # ── Internal state machine ────────────────────────────────────────────────

    async def _resolve_and_trigger(
        self,
        scene_id: str,
        changed_channel_id: str,
        is_playing: bool,
        resume_delay: float,
    ) -> None:
        new_active = self._get_active_interrupt(scene_id)
        current_active = self._active_interrupt.get(scene_id)

        if new_active == current_active:
            # Same active source — re-trigger refresh only if content changed on the
            # currently displayed interrupt (new track on same channel).
            if new_active and new_active == changed_channel_id and is_playing:
                logger.debug(
                    "interrupt.content_refresh scene=%s channel=%s",
                    scene_id,
                    new_active,
                )
                await self._trigger_interrupt_refresh(scene_id, new_active)
            return

        logger.info(
            "interrupt.transition scene=%s %s → %s",
            scene_id,
            current_active or "base",
            new_active or "base",
        )
        self._active_interrupt[scene_id] = new_active

        if new_active:
            self._cancel_resume(scene_id)
            await self._trigger_interrupt_refresh(scene_id, new_active)
        else:
            self._schedule_resume(scene_id, resume_delay)

    def _get_active_interrupt(self, scene_id: str) -> str | None:
        """Resolve the priority stack: return the highest-priority is_playing channel, or None."""
        candidates = [
            (info["priority"], info["last_ts"], ch_id)
            for ch_id, info in self._scene_state.get(scene_id, {}).items()
            if info.get("is_playing")
        ]
        if not candidates:
            return None
        # Highest priority first; most-recent timestamp breaks ties
        candidates.sort(key=lambda x: (-x[0], -x[1]))
        return candidates[0][2]

    # ── Refresh triggers ──────────────────────────────────────────────────────

    async def _trigger_interrupt_refresh(self, scene_id: str, channel_id: str) -> None:
        from app.services.scene_refresh_service import (
            scene_refresh_service,  # avoid circular
        )
        logger.info("interrupt.trigger_refresh scene=%s override_channel=%s", scene_id, channel_id)
        self._spawn(
            scene_refresh_service.refresh_scene(
                scene_id,
                trigger_reason="interrupt",
                force=True,
                channel_override_entry={"channel_id": channel_id},
            )
        )

    # ── Resume timer ──────────────────────────────────────────────────────────

    def _schedule_resume(self, scene_id: str, delay: float) -> None:
        self._cancel_resume(scene_id)
        logger.debug("interrupt.resume_scheduled scene=%s delay=%.1fs", scene_id, delay)
        self._resume_tasks[scene_id] = asyncio.create_task(
            self._resume_after_delay(scene_id, delay)
        )

    async def _resume_after_delay(self, scene_id: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.debug("interrupt.resume_cancelled scene=%s", scene_id)
            return

        # Confirm nothing became active while we were waiting
        if self._get_active_interrupt(scene_id) is not None:
            logger.debug("interrupt.resume_aborted scene=%s new_interrupt_active", scene_id)
            return

        logger.info("interrupt.resume_base scene=%s", scene_id)
        self._active_interrupt[scene_id] = None
        from app.services.scene_refresh_service import scene_refresh_service
        self._spawn(
            scene_refresh_service.refresh_scene(
                scene_id,
                trigger_reason="interrupt_cleared",
                force=True,
            )
        )

    def _spawn(self, coro: Any) -> asyncio.Task:
        """Create a task and hold a strong reference until it completes.

        Without this, the event loop's weak reference to the task is the only
        thing keeping it alive, risking GC-cancellation mid-execution.
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)

        def _on_done(t: asyncio.Task) -> None:
            self._background_tasks.discard(t)
            if not t.cancelled():
                exc = t.exception()
                if exc:
                    logger.error("interrupt.background_task_failed error=%s", exc, exc_info=exc)

        task.add_done_callback(_on_done)
        return task

    def _cancel_resume(self, scene_id: str) -> None:
        task = self._resume_tasks.pop(scene_id, None)
        if task and not task.done():
            task.cancel()


now_playing_interrupt_service = NowPlayingInterruptService()
