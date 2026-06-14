"""
Integration Tests for the HTTP API
Exercises health, channels, and scenes endpoints through the real app
"""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.services.deps import get_plugin_discovery_service


class StubPluginDiscovery:
    def __init__(self, plugins=None):
        self._plugins = plugins or []

    def get_all_plugins(self):
        return self._plugins


def make_fake_plugin(tmp_path, plugin_id="test-channel", version="1.2.3"):
    config_path = tmp_path / f"{plugin_id}-config.json"
    config_path.write_text(json.dumps({"version": version}))
    return SimpleNamespace(
        id=plugin_id,
        name="Test Channel",
        description="A test channel",
        icon="tv",
        healthy=True,
        config_path=str(config_path),
        plugin_path=tmp_path / plugin_id,
    )


@pytest.mark.integration
@pytest.mark.api
class TestHealthAPI:
    def test_health_returns_component_breakdown(self, client: TestClient):
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        for component in ("database", "redis", "mqtt", "websocket", "scheduler"):
            assert "status" in data[component]


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.channels
class TestChannelsAPI:
    def test_list_channels_empty(self, app, client: TestClient):
        app.dependency_overrides[get_plugin_discovery_service] = lambda: StubPluginDiscovery()

        response = client.get("/api/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["channels"] == []
        assert data["total"] == 0

    def test_list_channels_with_plugin(self, app, client: TestClient, tmp_path):
        plugin = make_fake_plugin(tmp_path)
        app.dependency_overrides[get_plugin_discovery_service] = lambda: StubPluginDiscovery([plugin])

        response = client.get("/api/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        entry = data["channels"][0]
        assert entry["id"] == "test-channel"
        assert entry["name"] == "Test Channel"
        assert entry["version"] == "1.2.3"
        assert entry["healthy"] is True


@pytest.mark.integration
@pytest.mark.api
class TestDisplayUnpair:
    def test_delete_display(self, client: TestClient, seeded_display):
        response = client.delete(f"/api/displays/{seeded_display.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["display_id"] == seeded_display.id
        assert "deleted" in data["message"].lower()

    def test_deleted_display_gone_from_db(self, client: TestClient, seeded_display, test_db_session):
        from app.db.models import DisplayClient

        client.delete(f"/api/displays/{seeded_display.id}")

        remaining = test_db_session.query(DisplayClient).filter(
            DisplayClient.id == seeded_display.id
        ).first()
        assert remaining is None

    def test_delete_display_cleans_related_records(self, client: TestClient, seeded_display, test_db_session):
        import datetime

        from app.db.models import ContentLease

        lease = ContentLease(
            lease_id="lease-1",
            display_id=seeded_display.id,
            scene_id="some-scene",
            content_id="content-1",
            expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
            distribution_mode="MIRROR",
        )
        test_db_session.add(lease)
        test_db_session.commit()

        response = client.delete(f"/api/displays/{seeded_display.id}")

        assert response.status_code == 200
        assert response.json()["deleted_content_leases"] == 1
        assert test_db_session.query(ContentLease).count() == 0

    def test_delete_unknown_display_404(self, client: TestClient):
        response = client.delete("/api/displays/never-existed")

        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.api
class TestScenesAPI:
    def test_list_scenes_empty(self, client: TestClient):
        response = client.get("/api/scenes")

        assert response.status_code == 200
        data = response.json()
        assert data["scenes"] == []
        assert data["total"] == 0
        assert data["limit"] == 100
        assert data["offset"] == 0

    def test_create_scene(self, client: TestClient, sample_scene_payload):
        response = client.post("/api/scenes", json=sample_scene_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-scene"
        assert data["name"] == "Test Scene"
        assert data["distribution_mode"] == "MIRROR"

    def test_create_scene_generates_id(self, client: TestClient, sample_scene_payload):
        sample_scene_payload.pop("id")

        response = client.post("/api/scenes", json=sample_scene_payload)

        assert response.status_code == 200
        assert response.json()["id"]

    def test_list_scenes_with_data(self, client: TestClient, seeded_scene):
        response = client.get("/api/scenes")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["scenes"][0]["id"] == seeded_scene.id
        assert data["scenes"][0]["name"] == "Seeded Scene"

    def test_list_scenes_pagination_echo(self, client: TestClient, seeded_scene):
        response = client.get("/api/scenes?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_get_scene_by_id(self, client: TestClient, seeded_scene):
        response = client.get(f"/api/scenes/{seeded_scene.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == seeded_scene.id
        # SceneResponse normalizes channel entries, padding optional fields
        assert [c["channel_id"] for c in data["channels"]] == ["test-channel"]

    def test_get_scene_not_found(self, client: TestClient):
        response = client.get("/api/scenes/missing-scene")

        assert response.status_code == 404
        assert "detail" in response.json()

    def test_update_scene(self, client: TestClient, seeded_scene):
        response = client.put(
            f"/api/scenes/{seeded_scene.id}",
            json={"name": "Renamed Scene"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Renamed Scene"

    def test_update_scene_not_found(self, client: TestClient):
        response = client.put("/api/scenes/missing-scene", json={"name": "X"})

        assert response.status_code == 404

    def test_delete_scene(self, client: TestClient, seeded_scene):
        response = client.delete(f"/api/scenes/{seeded_scene.id}")

        assert response.status_code == 200
        assert "deleted" in response.json()["message"]

        follow_up = client.get(f"/api/scenes/{seeded_scene.id}")
        assert follow_up.status_code == 404

    def test_delete_scene_not_found(self, client: TestClient):
        response = client.delete("/api/scenes/missing-scene")

        assert response.status_code == 404

    def test_activate_scene(self, client: TestClient, seeded_scene):
        response = client.post(f"/api/scenes/{seeded_scene.id}/activate")

        assert response.status_code == 200

        # SceneResponse serializes by alias, hence isActive
        data = client.get(f"/api/scenes/{seeded_scene.id}").json()
        assert data["isActive"] is True

    def test_activate_scene_not_found(self, client: TestClient):
        response = client.post("/api/scenes/missing-scene/activate")

        assert response.status_code == 404
