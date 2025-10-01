import json
import pytest
from app.services import mqtt_ws_bridge


class DummyWebSocketManager:
    def __init__(self):
        self.events = []

    async def emit_event(self, event: str, data, dashboards_only: bool = False, targets=None):  # noqa: D401
        self.events.append({
            "event": event,
            "data": data,
            "dashboards_only": dashboards_only,
            "targets": targets,
        })


@pytest.mark.asyncio
async def test_forward_json_parsed(monkeypatch):
    dummy = DummyWebSocketManager()
    monkeypatch.setattr(mqtt_ws_bridge, "websocket_manager", dummy)

    await mqtt_ws_bridge.forward_mqtt_message(
        topic="mimir/device1/status",
        payload_bytes=json.dumps({"status": "online"}).encode(),
        qos=1,
        retain=True,
    )

    assert len(dummy.events) == 1
    evt = dummy.events[0]
    assert evt["event"] == "mqtt_message"
    assert evt["data"]["topic"] == "mimir/device1/status"
    assert evt["data"]["payload"] == {"status": "online"}
    assert evt["data"]["raw_payload"] == json.dumps({"status": "online"})


@pytest.mark.asyncio
async def test_forward_raw_fallback(monkeypatch):
    dummy = DummyWebSocketManager()
    monkeypatch.setattr(mqtt_ws_bridge, "websocket_manager", dummy)

    await mqtt_ws_bridge.forward_mqtt_message(
        topic="mimir/device1/heartbeat",
        payload_bytes=b"not-json",
    )

    assert len(dummy.events) == 1
    evt = dummy.events[0]
    assert evt["data"]["payload"] == "not-json"
    assert evt["data"]["raw_payload"] == "not-json"


@pytest.mark.asyncio
async def test_filtered_out(monkeypatch):
    dummy = DummyWebSocketManager()
    monkeypatch.setattr(mqtt_ws_bridge, "websocket_manager", dummy)

    await mqtt_ws_bridge.forward_mqtt_message(
        topic="other/device1/status",
        payload_bytes=b"{}",
    )

    assert dummy.events == []
