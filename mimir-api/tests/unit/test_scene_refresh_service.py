"""Unit tests for SceneRefreshService.

Covers two known failure modes:
  - reload-loop  : fingerprint gating suppresses re-sending unchanged content
  - hairpin URL  : HTTP helper must use settings.internal_api_base_url, not public_base_url

Also covers static helpers and early-exit guard paths in refresh_scene.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.scene_refresh_service as srs_module
from app.services.scene_refresh_service import SceneRefreshResult, SceneRefreshService


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _cm(db_mock):
    """Wrap a db mock in a fake context-manager returned by SessionLocal()."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db_mock)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _scene(scene_id="s1", channels=None, distribution_mode="MIRROR"):
    s = MagicMock()
    s.id = scene_id
    s.channels = channels if channels is not None else [{"channel_id": "photo-frame"}]
    s.distribution_mode = distribution_mode
    s.content_hash = None
    s.content_epoch = None
    return s


@pytest.fixture()
def service():
    return SceneRefreshService()


@pytest.fixture(autouse=True)
def clear_fingerprints(monkeypatch):
    """Isolate the module-level fingerprint cache between tests."""
    monkeypatch.setattr(srs_module, "_last_scene_fingerprint", {})


# ---------------------------------------------------------------------------
# SceneRefreshResult
# ---------------------------------------------------------------------------

class TestSceneRefreshResult:
    def test_to_dict_normalizes_none_errors_to_empty_list(self):
        r = SceneRefreshResult(scene_id="x", status="ok", reason="test")
        assert r.to_dict()["errors"] == []

    def test_to_dict_preserves_error_list(self):
        r = SceneRefreshResult(scene_id="x", status="error", reason="t", errors=["oops"])
        d = r.to_dict()
        assert d["status"] == "error"
        assert d["errors"] == ["oops"]


# ---------------------------------------------------------------------------
# _parse_resolution_string
# ---------------------------------------------------------------------------

class TestParseResolution:
    def test_standard_landscape(self):
        assert SceneRefreshService._parse_resolution_string("800x480") == (800, 480)

    def test_portrait(self):
        assert SceneRefreshService._parse_resolution_string("480x800") == (480, 800)

    def test_uppercase_x_returns_default(self):
        # The check "x" not in res_str is case-sensitive, so uppercase X falls through to default
        assert SceneRefreshService._parse_resolution_string("1280X720") == (800, 480)

    def test_none_returns_default(self):
        assert SceneRefreshService._parse_resolution_string(None) == (800, 480)

    def test_missing_x_returns_default(self):
        assert SceneRefreshService._parse_resolution_string("1920") == (800, 480)

    def test_zero_width_returns_default(self):
        assert SceneRefreshService._parse_resolution_string("0x480") == (800, 480)

    def test_negative_dimension_returns_default(self):
        assert SceneRefreshService._parse_resolution_string("-1x480") == (800, 480)


# ---------------------------------------------------------------------------
# _append_cache_buster
# ---------------------------------------------------------------------------

class TestAppendCacheBuster:
    def test_adds_v_to_bare_url(self):
        url = SceneRefreshService._append_cache_buster("http://host/img.jpg", "abc")
        assert url == "http://host/img.jpg?v=abc"

    def test_appends_alongside_existing_query(self):
        url = SceneRefreshService._append_cache_buster("http://host/img.jpg?x=1", "abc")
        assert "v=abc" in url
        assert "x=1" in url

    def test_replaces_existing_v_param(self):
        url = SceneRefreshService._append_cache_buster("http://host/img.jpg?v=old", "new")
        assert "v=new" in url
        assert "old" not in url

    def test_custom_param_name(self):
        url = SceneRefreshService._append_cache_buster("http://host/img.jpg", "fp", param="hash")
        assert "hash=fp" in url
        assert "v=" not in url

    def test_path_without_scheme(self):
        url = SceneRefreshService._append_cache_buster("/swap/img.jpg", "fp42")
        assert "fp42" in url


# ---------------------------------------------------------------------------
# _convert_image_to_url
# ---------------------------------------------------------------------------

class TestConvertImageToUrl:
    @pytest.fixture()
    def svc(self, monkeypatch):
        monkeypatch.setattr(
            srs_module,
            "settings",
            SimpleNamespace(public_base_url="http://oak.local:5000"),
        )
        return SceneRefreshService()

    def test_channels_path_kept(self, svc):
        result = svc._convert_image_to_url({"image": "/channels/photo_frame/latest.jpg"})
        assert result == "http://oak.local:5000/channels/photo_frame/latest.jpg"

    def test_root_path_prefixed_with_channels(self, svc):
        result = svc._convert_image_to_url({"image": "/img.jpg"})
        assert result == "http://oak.local:5000/channels/img.jpg"

    def test_long_base64_string_returns_none(self, svc):
        assert svc._convert_image_to_url({"image": "A" * 200}) is None

    def test_filename_key_builds_photo_frame_url(self, svc):
        result = svc._convert_image_to_url({"filename": "photo.jpg"})
        assert result == "http://oak.local:5000/channels/photo_frame/uploads/photo.jpg"

    def test_empty_dict_returns_none(self, svc):
        assert svc._convert_image_to_url({}) is None


# ---------------------------------------------------------------------------
# refresh_scene — early-exit guards
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRefreshSceneEarlyExits:
    def _patch_db(self, monkeypatch, scene):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = scene
        monkeypatch.setattr(srs_module, "SessionLocal", MagicMock(return_value=_cm(db)))

    async def test_locked_skips_without_force(self, service):
        lock = service._get_lock("lock-scene")
        await lock.acquire()
        try:
            result = await service.refresh_scene("lock-scene", trigger_reason="test")
        finally:
            lock.release()
        assert result.status == "skipped"
        assert result.skipped_reason == "locked"

    async def test_scene_not_found_returns_error(self, service, monkeypatch):
        self._patch_db(monkeypatch, scene=None)
        result = await service.refresh_scene("missing", trigger_reason="test")
        assert result.status == "error"
        assert "scene_not_found" in result.errors

    async def test_no_channels_skips(self, service, monkeypatch):
        self._patch_db(monkeypatch, scene=_scene(channels=[]))
        result = await service.refresh_scene("s1", trigger_reason="test")
        assert result.status == "skipped"
        assert result.skipped_reason == "no_channels"

    async def test_channel_subset_no_match_skips(self, service, monkeypatch):
        self._patch_db(monkeypatch, scene=_scene(channels=[{"channel_id": "photo-frame"}]))
        result = await service.refresh_scene(
            "s1", trigger_reason="test", channel_subset=["other-ch"]
        )
        assert result.status == "skipped"
        assert result.skipped_reason == "no_matching_channels"

    async def test_no_assigned_displays_skips(self, service, monkeypatch):
        self._patch_db(monkeypatch, scene=_scene())
        monkeypatch.setattr(service, "_collect_assigned_displays", lambda s: [])
        result = await service.refresh_scene("s1", trigger_reason="test")
        assert result.status == "skipped"
        assert result.skipped_reason == "no_assigned_displays"

    async def test_target_devices_no_match_skips(self, service, monkeypatch):
        self._patch_db(monkeypatch, scene=_scene())
        monkeypatch.setattr(service, "_collect_assigned_displays", lambda s: [
            {"device_id": "device-a", "width": 800, "height": 480, "orientation": "landscape"}
        ])
        result = await service.refresh_scene(
            "s1", trigger_reason="test", target_devices=["device-b"]
        )
        assert result.status == "skipped"
        assert result.skipped_reason == "no_matching_target"


# ---------------------------------------------------------------------------
# Fingerprint gating — reload-loop prevention
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFingerprintGating:
    """
    The reload-loop bug: the scheduler kept sending the same image to displays every tick.
    _last_scene_fingerprint gates out identical content by comparing the response fingerprint
    (from X-Content-Fingerprint header or computed sha256) with the last-seen value.
    """

    def _setup(self, monkeypatch, service, fp="deadbeef"):
        """Patch all side-effecting dependencies to reach the fingerprint comparison."""
        scene = _scene("s1", channels=[{"channel_id": "photo-frame"}], distribution_mode="MIRROR")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = scene
        monkeypatch.setattr(srs_module, "SessionLocal", MagicMock(return_value=_cm(db)))

        monkeypatch.setattr(service, "_collect_assigned_displays", lambda s: [
            {"device_id": "disp-a", "width": 800, "height": 480, "orientation": "landscape"}
        ])

        fake_plugin = SimpleNamespace(instance=MagicMock())
        monkeypatch.setattr(
            "app.services.plugin_discovery.plugin_discovery_service",
            SimpleNamespace(get_plugin=lambda _: fake_plugin),
        )

        monkeypatch.setattr(
            service,
            "_request_channel_image_http",
            AsyncMock(return_value=(b"img-bytes", "image/png", fp)),
        )
        monkeypatch.setattr(
            srs_module, "save_swap_image",
            MagicMock(return_value=(None, "http://oak.local:5000/swap/s1/img.png", True)),
        )
        monkeypatch.setattr(srs_module.mqtt_scene_service, "send_display_image", AsyncMock(return_value=True))
        monkeypatch.setattr(srs_module, "DisplayImagePersistenceService", MagicMock())

    async def test_same_fingerprint_skips_unchanged_content(self, service, monkeypatch):
        fp = "abcdef01"
        self._setup(monkeypatch, service, fp=fp)
        srs_module._last_scene_fingerprint["s1:"] = fp

        result = await service.refresh_scene("s1", trigger_reason="scheduler")

        assert result.status == "skipped"
        assert result.skipped_reason == "unchanged_content"

    async def test_different_fingerprint_sends_update(self, service, monkeypatch):
        self._setup(monkeypatch, service, fp="new-fp")
        srs_module._last_scene_fingerprint["s1:"] = "old-fp"

        result = await service.refresh_scene("s1", trigger_reason="scheduler")

        assert result.status == "ok"
        assert result.displays_updated == 1

    async def test_force_bypasses_fingerprint_gate(self, service, monkeypatch):
        fp = "same-fp"
        self._setup(monkeypatch, service, fp=fp)
        srs_module._last_scene_fingerprint["s1:"] = fp

        result = await service.refresh_scene("s1", trigger_reason="manual", force=True)

        assert result.status == "ok"
        assert result.displays_updated == 1

    async def test_no_prior_fingerprint_sends_first_update(self, service, monkeypatch):
        self._setup(monkeypatch, service, fp="brand-new-fp")

        result = await service.refresh_scene("s1", trigger_reason="push")

        assert result.status == "ok"
        assert result.displays_updated == 1

    async def test_fingerprint_stored_after_successful_send(self, service, monkeypatch):
        fp = "content-fp"
        self._setup(monkeypatch, service, fp=fp)

        await service.refresh_scene("s1", trigger_reason="push")

        assert srs_module._last_scene_fingerprint.get("s1:") == fp


# ---------------------------------------------------------------------------
# Hairpin URL fix
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHairpinFix:
    """
    The hairpin bug: channel HTTP requests used public_base_url (e.g. http://oak.local:5000),
    which timed out after 15 s from inside bridge-networked containers.
    Fix: _request_channel_image_http_blocking uses settings.internal_api_base_url instead.
    """

    def _intercept(self, monkeypatch):
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.full_url)
            raise srs_module._urlerr.URLError("test-abort")

        monkeypatch.setattr(
            srs_module,
            "settings",
            SimpleNamespace(
                internal_api_base_url="http://localhost:5000",
                public_base_url="http://oak.local:5000",
                channel_http_timeout_seconds=15,
            ),
        )
        monkeypatch.setattr(srs_module._urlreq, "urlopen", fake_urlopen)
        return captured

    def test_uses_internal_not_public_base_url(self, service, monkeypatch):
        captured = self._intercept(monkeypatch)

        with pytest.raises(RuntimeError):
            service._request_channel_image_http_blocking("photo-frame", {})

        assert captured[0].startswith("http://localhost:5000")
        assert "oak.local" not in captured[0]

    def test_targets_channel_request_image_endpoint(self, service, monkeypatch):
        captured = self._intercept(monkeypatch)

        with pytest.raises(RuntimeError):
            service._request_channel_image_http_blocking("spotify", {})

        assert captured[0] == "http://localhost:5000/api/channels/spotify/request-image"

    def test_http_error_wrapped_in_runtime_error(self, service, monkeypatch):
        def fake_urlopen(req, timeout=None):
            raise srs_module._urlerr.HTTPError(req.full_url, 404, "Not Found", {}, None)

        monkeypatch.setattr(
            srs_module, "settings",
            SimpleNamespace(internal_api_base_url="http://localhost:5000", channel_http_timeout_seconds=15),
        )
        monkeypatch.setattr(srs_module._urlreq, "urlopen", fake_urlopen)

        with pytest.raises(RuntimeError, match="http_404"):
            service._request_channel_image_http_blocking("photo-frame", {})

    def test_url_error_wrapped_in_runtime_error(self, service, monkeypatch):
        def fake_urlopen(req, timeout=None):
            raise srs_module._urlerr.URLError("Connection refused")

        monkeypatch.setattr(
            srs_module, "settings",
            SimpleNamespace(internal_api_base_url="http://localhost:5000", channel_http_timeout_seconds=15),
        )
        monkeypatch.setattr(srs_module._urlreq, "urlopen", fake_urlopen)

        with pytest.raises(RuntimeError, match="url_error"):
            service._request_channel_image_http_blocking("photo-frame", {})
