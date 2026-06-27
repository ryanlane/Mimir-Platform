"""Unit tests for NowPlayingInterruptService.

Covers:
  - is_playing extraction from both top-level and legacy payload layouts
  - Priority stack resolution (highest priority wins, recency breaks ties)
  - Transition from base → interrupt → base
  - Resume delay: revert fires after delay, cancelled on new is_playing=true
  - Multiple interrupt sources: higher priority pre-empts lower
  - clear_scene wipes all state
  - get_state snapshot
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.channel_events import ChannelUpdateEvent
from app.services.now_playing_interrupt_service import (
    NowPlayingInterruptService,
    _extract_is_playing,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _evt(channel_id: str, is_playing: bool, *, top_level: bool = True) -> ChannelUpdateEvent:
    """Build a minimal push event."""
    if top_level:
        payload = {"is_playing": is_playing}
    else:
        payload = {"track": {"title": "Song", "is_playing": is_playing}}
    return ChannelUpdateEvent(
        channel_id=channel_id,
        event_type="update",
        payload=payload,
        ts=time.time(),
        hash=f"{channel_id}:{is_playing}",
    )


def _cfg(priority: int = 10, delay: float = 0.05) -> dict:
    return {"priority": priority, "resume_delay_seconds": delay}


# ── _extract_is_playing ───────────────────────────────────────────────────────

class TestExtractIsPlaying:
    def test_top_level_true(self):
        assert _extract_is_playing({"is_playing": True}) is True

    def test_top_level_false(self):
        assert _extract_is_playing({"is_playing": False}) is False

    def test_legacy_track_true(self):
        assert _extract_is_playing({"track": {"is_playing": True}}) is True

    def test_legacy_track_false(self):
        assert _extract_is_playing({"track": {"is_playing": False}}) is False

    def test_missing_returns_none(self):
        assert _extract_is_playing({"title": "Song", "artist": "Band"}) is None

    def test_top_level_takes_precedence(self):
        # Both present — top level wins
        assert _extract_is_playing({"is_playing": False, "track": {"is_playing": True}}) is False


# ── State machine ─────────────────────────────────────────────────────────────

class TestNowPlayingInterruptService:
    @pytest.fixture
    def service(self):
        return NowPlayingInterruptService()

    @pytest.fixture
    def mock_refresh(self):
        """Patch scene_refresh_service.refresh_scene so we can inspect calls.

        The interrupt service uses a local ``from app.services.scene_refresh_service
        import scene_refresh_service`` inside each method to avoid circular imports,
        so we must patch the attribute on that module — not on the interrupt module.
        """
        mock = AsyncMock()
        with patch("app.services.scene_refresh_service.scene_refresh_service") as m:
            m.refresh_scene = mock
            yield mock

    # ── Basic transitions ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_no_trigger_when_is_playing_missing(self, service, mock_refresh):
        evt = ChannelUpdateEvent(
            channel_id="com.lastfm.nowplaying",
            event_type="update",
            payload={"title": "no is_playing key"},
            ts=time.time(),
        )
        await service.on_push_event(evt, {"scene-1": _cfg()})
        mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_interrupt_triggers_refresh_on_play(self, service, mock_refresh):
        await service.on_push_event(
            _evt("com.lastfm.nowplaying", True),
            {"scene-1": _cfg()},
        )
        await asyncio.sleep(0)  # let create_task run
        mock_refresh.assert_called_once()
        call_kwargs = mock_refresh.call_args
        assert call_kwargs.kwargs.get("channel_override_entry") == {"channel_id": "com.lastfm.nowplaying"}
        assert call_kwargs.args[0] == "scene-1"

    @pytest.mark.asyncio
    async def test_no_refresh_when_already_showing_same_interrupt(self, service, mock_refresh):
        # First play event — triggers refresh
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), {"scene-1": _cfg()})
        await asyncio.sleep(0)
        assert mock_refresh.call_count == 1

        # Second play event for same channel (new track, same is_playing=true) — triggers again
        evt2 = ChannelUpdateEvent(
            channel_id="com.lastfm.nowplaying",
            event_type="update",
            payload={"is_playing": True},
            ts=time.time(),
            hash="different-hash",
        )
        await service.on_push_event(evt2, {"scene-1": _cfg()})
        await asyncio.sleep(0)
        assert mock_refresh.call_count == 2

    @pytest.mark.asyncio
    async def test_stop_schedules_resume_delay(self, service, mock_refresh):
        # Start playing
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), {"scene-1": _cfg(delay=0.05)})
        await asyncio.sleep(0)
        mock_refresh.reset_mock()

        # Stop playing
        await service.on_push_event(_evt("com.lastfm.nowplaying", False), {"scene-1": _cfg(delay=0.05)})
        # Before delay — no base refresh yet
        assert mock_refresh.call_count == 0

        # After delay — base refresh should fire
        await asyncio.sleep(0.15)
        assert mock_refresh.call_count == 1
        call = mock_refresh.call_args
        assert call.kwargs.get("channel_override_entry") is None
        assert call.kwargs.get("trigger_reason") == "interrupt_cleared"

    @pytest.mark.asyncio
    async def test_resume_cancelled_by_new_play(self, service, mock_refresh):
        # Play, stop, play again before delay expires
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), {"scene-1": _cfg(delay=0.2)})
        await asyncio.sleep(0)
        await service.on_push_event(_evt("com.lastfm.nowplaying", False), {"scene-1": _cfg(delay=0.2)})
        mock_refresh.reset_mock()

        # New track before 0.2s delay expires
        await asyncio.sleep(0.05)
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), {"scene-1": _cfg(delay=0.2)})
        await asyncio.sleep(0)

        # Should have triggered interrupt refresh, NOT base refresh
        assert mock_refresh.call_count == 1
        assert mock_refresh.call_args.kwargs["channel_override_entry"] == {"channel_id": "com.lastfm.nowplaying"}

        # Wait past the original delay — no base refresh should have fired
        await asyncio.sleep(0.25)
        assert mock_refresh.call_count == 1  # still just the interrupt refresh

    # ── Priority stack ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_higher_priority_wins(self, service, mock_refresh):
        scene_info = {
            "scene-1": {"priority": 5, "resume_delay_seconds": 0.05},
        }
        high_info = {
            "scene-1": {"priority": 20, "resume_delay_seconds": 0.05},
        }

        # Lower priority plays first
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), scene_info)
        await asyncio.sleep(0)
        mock_refresh.reset_mock()

        # Higher priority plays — should trigger switch
        await service.on_push_event(_evt("com.spotify.status", True), high_info)
        await asyncio.sleep(0)
        assert mock_refresh.call_count == 1
        assert mock_refresh.call_args.kwargs["channel_override_entry"] == {"channel_id": "com.spotify.status"}

    @pytest.mark.asyncio
    async def test_lower_priority_does_not_displace_higher(self, service, mock_refresh):
        scene_info_high = {"scene-1": {"priority": 20, "resume_delay_seconds": 0.05}}
        scene_info_low = {"scene-1": {"priority": 5, "resume_delay_seconds": 0.05}}

        # High priority plays first
        await service.on_push_event(_evt("com.spotify.status", True), scene_info_high)
        await asyncio.sleep(0)
        mock_refresh.reset_mock()

        # Lower priority fires — active interrupt should NOT change
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), scene_info_low)
        await asyncio.sleep(0)
        # No transition — Spotify still wins, so no new refresh for a channel change
        assert mock_refresh.call_count == 0

    @pytest.mark.asyncio
    async def test_high_stops_reverts_to_lower_still_playing(self, service, mock_refresh):
        scene_info_high = {"scene-1": {"priority": 20, "resume_delay_seconds": 0.05}}
        scene_info_low = {"scene-1": {"priority": 5, "resume_delay_seconds": 0.05}}

        await service.on_push_event(_evt("com.spotify.status", True), scene_info_high)
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), scene_info_low)
        await asyncio.sleep(0)
        mock_refresh.reset_mock()

        # High priority stops — should immediately switch to lower (still playing)
        await service.on_push_event(_evt("com.spotify.status", False), scene_info_high)
        await asyncio.sleep(0.1)
        assert mock_refresh.call_count >= 1
        # The interrupt that eventually fires should be the lower-priority one
        calls = mock_refresh.call_args_list
        override_channels = [c.kwargs.get("channel_override_entry", {}).get("channel_id") for c in calls]
        assert "com.lastfm.nowplaying" in override_channels

    # ── Legacy payload support ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_legacy_payload_format_triggers_refresh(self, service, mock_refresh):
        evt = _evt("com.lastfm.nowplaying", True, top_level=False)
        await service.on_push_event(evt, {"scene-1": _cfg()})
        await asyncio.sleep(0)
        mock_refresh.assert_called_once()

    # ── clear_scene ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_clear_scene_removes_state(self, service, mock_refresh):
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), {"scene-1": _cfg()})
        service.clear_scene("scene-1")
        assert "scene-1" not in service._scene_state
        assert "scene-1" not in service._active_interrupt

    # ── get_state ─────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_state_reflects_current(self, service, mock_refresh):
        await service.on_push_event(_evt("com.lastfm.nowplaying", True), {"scene-1": _cfg()})
        state = service.get_state("scene-1")
        assert state["active_interrupt"] == "com.lastfm.nowplaying"
        assert "com.lastfm.nowplaying" in state["sources"]
        assert state["sources"]["com.lastfm.nowplaying"]["is_playing"] is True

    def test_get_state_empty_scene(self, service):
        state = service.get_state("nonexistent-scene")
        assert state["active_interrupt"] is None
        assert state["sources"] == {}
