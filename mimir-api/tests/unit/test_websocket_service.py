"""
Unit Tests for WebSocketManager
Tests connection lifecycle, broadcasting, and the event envelope
"""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.services.websocket_manager import WebSocketManager


class FakeWebSocket:
    """Minimal stand-in for a starlette WebSocket."""

    def __init__(self, fail: bool = False):
        self.sent: list[str] = []
        self.accepted = False
        self.fail = fail

    async def accept(self):
        self.accepted = True

    async def send_text(self, message: str):
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append(message)

    def last_payload(self) -> dict:
        return json.loads(self.sent[-1])


@pytest.fixture()
def manager():
    mgr = WebSocketManager()
    # Avoid real database writes from display connect/disconnect
    mgr._update_display_status = AsyncMock()
    return mgr


@pytest.mark.unit
@pytest.mark.websocket
class TestConnectionLifecycle:
    def test_initial_state(self, manager):
        assert manager.active_connections == []
        assert manager.display_connections == {}
        assert manager.connection_metadata == {}
        assert manager.sequence_id == 0

    async def test_connect_dashboard(self, manager):
        ws = FakeWebSocket()
        await manager.connect_dashboard(ws)

        assert ws.accepted
        assert ws in manager.active_connections
        assert manager.connection_metadata[ws]["type"] == "dashboard"

    async def test_connect_legacy_alias(self, manager):
        ws = FakeWebSocket()
        await manager.connect(ws)

        assert manager.connection_metadata[ws]["type"] == "dashboard"

    async def test_connect_display(self, manager):
        ws = FakeWebSocket()
        await manager.connect_display(ws, "display-1")

        assert ws.accepted
        assert manager.display_connections["display-1"] is ws
        assert manager.connection_metadata[ws]["display_id"] == "display-1"
        manager._update_display_status.assert_awaited_once_with("display-1", True)

    async def test_disconnect_dashboard(self, manager):
        ws = FakeWebSocket()
        await manager.connect_dashboard(ws)

        manager.disconnect(ws)

        assert ws not in manager.active_connections
        assert ws not in manager.connection_metadata

    async def test_disconnect_display_clears_registration(self, manager):
        ws = FakeWebSocket()
        await manager.connect_display(ws, "display-1")

        manager.disconnect(ws)
        await asyncio.sleep(0)  # let the scheduled status update task run

        assert "display-1" not in manager.display_connections
        manager._update_display_status.assert_awaited_with("display-1", False)

    def test_disconnect_unknown_socket_is_noop(self, manager):
        manager.disconnect(FakeWebSocket())  # must not raise

    async def test_connection_stats(self, manager):
        await manager.connect_dashboard(FakeWebSocket())
        await manager.connect_display(FakeWebSocket(), "display-1")

        stats = manager.get_connection_stats()

        assert stats["total_connections"] == 2
        assert stats["dashboard_connections"] == 1
        assert stats["display_connections"] == 1
        assert stats["connected_displays"] == ["display-1"]
        assert manager.get_connected_clients_count() == 2


@pytest.mark.unit
@pytest.mark.websocket
class TestSequenceIds:
    def test_next_sequence_id_increments(self, manager):
        assert manager.next_sequence_id() == 1
        assert manager.next_sequence_id() == 2
        assert manager.get_current_sequence_id() == 2

    def test_legacy_increment_alias(self, manager):
        assert manager.increment_sequence_id() == 1


@pytest.mark.unit
@pytest.mark.websocket
class TestSendHelpers:
    async def test_send_personal_message_success(self, manager):
        ws = FakeWebSocket()
        await manager.connect_dashboard(ws)

        assert await manager.send_personal_message("hello", ws) is True
        assert ws.sent == ["hello"]

    async def test_send_personal_message_failure_disconnects(self, manager):
        ws = FakeWebSocket(fail=True)
        await manager.connect_dashboard(ws)

        assert await manager.send_personal_message("hello", ws) is False
        assert ws not in manager.active_connections

    async def test_send_to_display(self, manager):
        ws = FakeWebSocket()
        await manager.connect_display(ws, "display-1")

        assert await manager.send_to_display("msg", "display-1") is True
        assert ws.sent == ["msg"]

    async def test_send_to_unknown_display(self, manager):
        assert await manager.send_to_display("msg", "missing") is False


@pytest.mark.unit
@pytest.mark.websocket
class TestBroadcasts:
    async def test_broadcast_all(self, manager):
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        await manager.connect_dashboard(ws1)
        await manager.connect_display(ws2, "display-1")

        await manager.broadcast_all({"event": "x", "data": {}})

        assert len(ws1.sent) == 1
        assert len(ws2.sent) == 1

    async def test_broadcast_drops_failing_sockets(self, manager):
        good, bad = FakeWebSocket(), FakeWebSocket(fail=True)
        await manager.connect_dashboard(good)
        await manager.connect_dashboard(bad)

        await manager.broadcast_all({"event": "x"})

        assert bad not in manager.active_connections
        assert good in manager.active_connections

    async def test_broadcast_dashboards_only(self, manager):
        dash, disp = FakeWebSocket(), FakeWebSocket()
        await manager.connect_dashboard(dash)
        await manager.connect_display(disp, "display-1")

        await manager.broadcast_dashboards({"event": "x"})

        assert len(dash.sent) == 1
        assert disp.sent == []

    async def test_broadcast_displays_targeted(self, manager):
        d1, d2 = FakeWebSocket(), FakeWebSocket()
        await manager.connect_display(d1, "display-1")
        await manager.connect_display(d2, "display-2")

        await manager.broadcast_displays({"event": "x"}, display_ids=["display-2"])

        assert d1.sent == []
        assert len(d2.sent) == 1

    async def test_legacy_string_broadcast(self, manager):
        ws = FakeWebSocket()
        await manager.connect_dashboard(ws)

        await manager.broadcast("raw text")

        assert ws.sent == ["raw text"]


@pytest.mark.unit
@pytest.mark.websocket
class TestEventEnvelope:
    async def test_emit_event_to_targets(self, manager):
        ws = FakeWebSocket()
        await manager.connect_dashboard(ws)

        await manager.emit_event("ping", {"a": 1}, targets=[ws])

        payload = ws.last_payload()
        assert payload["event"] == "ping"
        assert payload["data"] == {"a": 1}
        assert "timestamp" in payload

    async def test_emit_event_with_sequence(self, manager):
        ws = FakeWebSocket()
        await manager.connect_dashboard(ws)

        await manager.emit_event("tick", {}, include_sequence=True, targets=[ws])

        assert ws.last_payload()["sequence_id"] == 1

    async def test_emit_event_audience_routing(self, manager):
        dash, disp = FakeWebSocket(), FakeWebSocket()
        await manager.connect_dashboard(dash)
        await manager.connect_display(disp, "display-1")

        await manager.emit_event("for-dash", {}, audience="dashboards")
        await manager.emit_event("for-disp", {}, audience="displays")

        assert dash.last_payload()["event"] == "for-dash"
        assert disp.last_payload()["event"] == "for-disp"
        assert len(dash.sent) == 1
        assert len(disp.sent) == 1

    async def test_notify_helpers_reach_all(self, manager):
        ws = FakeWebSocket()
        await manager.connect_dashboard(ws)

        await manager.notify_scene_change("scene-1")
        await manager.notify_display_status_change("display-1", {"online": True})
        await manager.notify_channel_update("channel-1")

        events = [json.loads(m)["event"] for m in ws.sent]
        assert events == ["scene_changed", "display_status_changed", "channel_updated"]


@pytest.mark.unit
@pytest.mark.websocket
class TestStructuredBroadcasts:
    async def test_scene_activation_goes_to_displays(self, manager):
        dash, disp = FakeWebSocket(), FakeWebSocket()
        await manager.connect_dashboard(dash)
        await manager.connect_display(disp, "display-1")

        await manager.broadcast_scene_activation("scene-1", {"name": "Scene"})

        assert dash.sent == []
        payload = disp.last_payload()
        assert payload["type"] == "scene_activation"
        assert payload["scene_id"] == "scene-1"
        assert payload["sequence_id"] == 1

    async def test_content_update_targeting(self, manager):
        d1, d2 = FakeWebSocket(), FakeWebSocket()
        await manager.connect_display(d1, "display-1")
        await manager.connect_display(d2, "display-2")

        await manager.broadcast_content_update({"url": "x"}, target_displays=["display-1"])

        assert len(d1.sent) == 1
        assert d2.sent == []
        assert d1.last_payload()["type"] == "content_update"

    async def test_heartbeat_reaches_everyone(self, manager):
        dash, disp = FakeWebSocket(), FakeWebSocket()
        await manager.connect_dashboard(dash)
        await manager.connect_display(disp, "display-1")

        await manager.broadcast_heartbeat()

        assert dash.last_payload()["type"] == "heartbeat"
        assert disp.last_payload()["type"] == "heartbeat"

    async def test_display_assignment_single_target(self, manager):
        d1, d2 = FakeWebSocket(), FakeWebSocket()
        await manager.connect_display(d1, "display-1")
        await manager.connect_display(d2, "display-2")

        await manager.broadcast_display_assignment("display-1", {"scene_id": "s"})

        assert len(d1.sent) == 1
        assert d2.sent == []
        assert d1.last_payload()["type"] == "display_assignment"
