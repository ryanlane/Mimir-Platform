"""
Unit Tests for FleetRolloutService
Covers canary promotion rules, manifest loading, and publish deduplication
"""
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services.fleet_rollout import (
    PROMOTE_AFTER_SECONDS,
    FleetRolloutService,
)


def display(display_id, version, online=True, canary=False):
    return SimpleNamespace(
        display_id=display_id,
        client_version=version,
        is_online=online,
        properties={"canary": "true"} if canary else {},
    )


@pytest.fixture()
def service():
    return FleetRolloutService()


@pytest.fixture()
def fleet(monkeypatch):
    """Install a fake mdns fleet; returns a dict the test can mutate."""
    from app.services.mdns_discovery import mdns_discovery_service

    displays = {}
    monkeypatch.setattr(mdns_discovery_service, "discovered_displays", displays, raising=False)
    return displays


@pytest.mark.unit
class TestFleetSnapshot:
    def test_offline_displays_excluded(self, service, fleet):
        fleet["a"] = display("a", "1.0.0", online=False, canary=True)
        fleet["b"] = display("b", "1.0.0", online=True)

        canaries, everyone = service._fleet_snapshot()

        assert canaries == []
        assert everyone == [("b", "1.0.0")]

    def test_canary_property_detected(self, service, fleet):
        fleet["c"] = display("c", "1.0.1", canary=True)

        canaries, everyone = service._fleet_snapshot()

        assert canaries == [("c", "1.0.1")]
        assert everyone == [("c", "1.0.1")]


@pytest.mark.unit
class TestDecidePhase:
    def test_no_online_canaries_goes_straight_to_all(self, service, fleet):
        fleet["a"] = display("a", "1.0.0")  # plain display, not canary

        assert service._decide_phase("1.0.7") == "all"
        assert service._canary_healthy_since is None

    def test_unconverged_canaries_hold_canary_phase(self, service, fleet):
        fleet["c"] = display("c", "1.0.5", canary=True)

        assert service._decide_phase("1.0.7") == "canary"
        assert service._canary_healthy_since is None

    def test_converged_canaries_wait_out_soak_period(self, service, fleet, monkeypatch):
        fleet["c"] = display("c", "1.0.7", canary=True)

        clock = {"now": 1000.0}
        monkeypatch.setattr(time, "monotonic", lambda: clock["now"])

        # First convergence starts the soak clock but stays in canary phase
        assert service._decide_phase("1.0.7") == "canary"
        assert service._canary_healthy_since == 1000.0

        # Still inside the soak window
        clock["now"] += PROMOTE_AFTER_SECONDS - 1
        assert service._decide_phase("1.0.7") == "canary"

        # Soak complete -> promote
        clock["now"] += 2
        assert service._decide_phase("1.0.7") == "all"

    def test_canary_regression_resets_soak_clock(self, service, fleet, monkeypatch):
        fleet["c"] = display("c", "1.0.7", canary=True)
        clock = {"now": 1000.0}
        monkeypatch.setattr(time, "monotonic", lambda: clock["now"])

        service._decide_phase("1.0.7")  # starts soak
        # Canary falls back to the old version (failed update rolled back)
        fleet["c"] = display("c", "1.0.5", canary=True)
        assert service._decide_phase("1.0.7") == "canary"
        assert service._canary_healthy_since is None

    def test_one_lagging_canary_blocks_promotion(self, service, fleet, monkeypatch):
        fleet["c1"] = display("c1", "1.0.7", canary=True)
        fleet["c2"] = display("c2", "1.0.5", canary=True)
        monkeypatch.setattr(time, "monotonic", lambda: 1000.0)

        assert service._decide_phase("1.0.7") == "canary"
        assert service._canary_healthy_since is None

    def test_version_prefix_normalized(self, service, fleet, monkeypatch):
        fleet["c"] = display("c", "v1.0.7", canary=True)

        clock = {"now": 1000.0}
        monkeypatch.setattr(time, "monotonic", lambda: clock["now"])

        assert service._decide_phase("v1.0.7") == "canary"  # converged, soaking
        clock["now"] += PROMOTE_AFTER_SECONDS + 1
        assert service._decide_phase("v1.0.7") == "all"


@pytest.mark.unit
class TestManifestLoading:
    def test_missing_manifest_returns_none(self, service, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "client_releases_dir", str(tmp_path), raising=False)

        assert service._load_latest_manifest() is None

    def test_invalid_json_returns_none(self, service, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "client_releases_dir", str(tmp_path), raising=False)
        latest = tmp_path / "latest"
        latest.mkdir()
        (latest / "manifest.json").write_text("{nope")

        assert service._load_latest_manifest() is None

    def test_valid_manifest_loaded(self, service, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "client_releases_dir", str(tmp_path), raising=False)
        latest = tmp_path / "latest"
        latest.mkdir()
        manifest = {"version": "1.0.7", "artifact": "mimir_display-1.0.7.tar.gz", "sha256": "abc"}
        (latest / "manifest.json").write_text(json.dumps(manifest))

        assert service._load_latest_manifest() == manifest


@pytest.mark.unit
class TestPublish:
    @pytest.fixture()
    def publisher(self, monkeypatch):
        from app.services.mqtt.publisher import MQTTSceneAssignmentPublisher

        stub = SimpleNamespace(publish_topic=AsyncMock(return_value=True))
        monkeypatch.setattr(MQTTSceneAssignmentPublisher, "get", classmethod(lambda cls: stub))
        return stub

    async def test_publish_payload_shape(self, service, publisher):
        manifest = {"version": "v1.0.7", "artifact": "a.tar.gz", "sha256": "abc"}

        await service._publish(manifest, "canary")

        publisher.publish_topic.assert_awaited_once()
        topic, payload = publisher.publish_topic.await_args.args
        assert topic == "mimir/fleet/desired_version"
        assert payload["version"] == "1.0.7"
        assert payload["download_path"] == "/api/client-releases/v1.0.7/download"
        assert payload["phase"] == "canary"
        assert payload["min_server_version"] == "0.0.0"
        assert publisher.publish_topic.await_args.kwargs == {"qos": 1, "retain": True}

    async def test_same_version_and_phase_published_once(self, service, publisher):
        manifest = {"version": "1.0.7", "artifact": "a", "sha256": "x"}

        await service._publish(manifest, "canary")
        await service._publish(manifest, "canary")

        assert publisher.publish_topic.await_count == 1

    async def test_phase_change_republishes(self, service, publisher):
        manifest = {"version": "1.0.7", "artifact": "a", "sha256": "x"}

        await service._publish(manifest, "canary")
        await service._publish(manifest, "all")

        assert publisher.publish_topic.await_count == 2

    async def test_failed_publish_retried_next_cycle(self, service, publisher):
        publisher.publish_topic.return_value = False
        manifest = {"version": "1.0.7", "artifact": "a", "sha256": "x"}

        await service._publish(manifest, "all")
        await service._publish(manifest, "all")

        # Not deduplicated because the first attempt never succeeded
        assert publisher.publish_topic.await_count == 2
