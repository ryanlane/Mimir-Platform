import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import mqtt_ws_bridge


class DummyWSMgr:
    def __init__(self):
        self.events = []

    async def emit_event(self, event: str, data: dict, audience: str = "all", display_ids=None, include_sequence: bool = False):
        self.events.append({
            "event": event,
            "data": data,
            "audience": audience,
        })


@pytest.fixture
def client(monkeypatch):
    dummy = DummyWSMgr()
    monkeypatch.setattr(mqtt_ws_bridge, "websocket_manager", dummy)
    # Ensure debug flag for endpoint gating
    monkeypatch.setattr("app.api.routes.debug_mqtt.settings", "debug", True, raising=False)
    return TestClient(app)


def test_echo_and_stats(client):  # type: ignore
    payload = {"hello": "world"}
    resp = client.post("/api/debug/mqtt/echo", json={"topic": "mimir/test/evt", "payload": payload})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["forwarded"] is True
    assert data["topic"] == "mimir/test/evt"

    # Stats should now include topic
    stats = client.get("/api/debug/mqtt/stats").json()
    assert stats["total_topics"] >= 1
    topics = [t["topic"] for t in stats["topics"]]
    assert "mimir/test/evt" in topics
