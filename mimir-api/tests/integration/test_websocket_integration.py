"""
Integration Tests for WebSocket Functionality
Exercises the /ws and /ws/display/{id} endpoints through the real app
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.websocket
class TestWebSocketStatusEndpoint:
    def test_status_shape(self, client: TestClient):
        response = client.get("/api/websocket/status")

        assert response.status_code == 200
        data = response.json()
        assert data["websocket_url"] == "/ws"
        assert isinstance(data["connected_clients"], int)
        assert isinstance(data["current_sequence_id"], int)
        assert data["features"]["generic_event_envelope"] is True


@pytest.mark.integration
@pytest.mark.websocket
class TestDashboardWebSocket:
    def test_ping_pong(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            ws.send_text('{"event": "ping"}')
            payload = ws.receive_json()

            assert payload["event"] == "pong"
            assert "timestamp" in payload

    def test_non_json_message_is_echoed(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            ws.send_text("plain text")
            payload = ws.receive_json()

            assert payload["event"] == "echo"
            assert payload["data"]["text"] == "plain text"

    def test_state_sync_request_returns_snapshot(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            ws.send_text('{"event": "state_sync_request"}')
            payload = ws.receive_json()

            assert payload["event"] == "state_snapshot"
            assert payload["data"]["total_connections"] >= 1

    def test_unknown_event_is_acknowledged(self, client: TestClient):
        with client.websocket_connect("/ws") as ws:
            ws.send_text('{"event": "bogus"}')
            payload = ws.receive_json()

            assert payload["event"] == "unknown_event"
            assert payload["data"]["original"] == {"event": "bogus"}

    def test_connection_counted_in_status(self, client: TestClient):
        with client.websocket_connect("/ws"):
            response = client.get("/api/websocket/status")
            assert response.json()["connected_clients"] >= 1


@pytest.mark.integration
@pytest.mark.websocket
class TestDisplayWebSocket:
    def test_unknown_display_event_acknowledged(self, client: TestClient):
        with client.websocket_connect("/ws/display/test-display-1") as ws:
            ws.send_text('{"event": "hello"}')
            payload = ws.receive_json()

            assert payload["event"] == "message_acknowledged"
            assert payload["data"]["display_id"] == "test-display-1"
            assert payload["data"]["original_event"] == "hello"

    def test_invalid_json_returns_error(self, client: TestClient):
        with client.websocket_connect("/ws/display/test-display-1") as ws:
            ws.send_text("{nope")
            payload = ws.receive_json()

            assert payload["event"] == "error"
            assert payload["data"]["message"] == "Invalid JSON"

    def test_display_listed_in_status_while_connected(self, client: TestClient):
        with client.websocket_connect("/ws/display/test-display-42"):
            response = client.get("/api/websocket/status")
            assert response.json()["connected_clients"] >= 1
