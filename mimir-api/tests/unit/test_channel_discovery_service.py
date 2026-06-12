"""
Unit Tests for ChannelDiscoveryService
Tests channel discovery, configuration loading, and SRI hash computation
"""
import base64
import hashlib
import json

import pytest
from fastapi import FastAPI

from app.services.channel_discovery import ChannelDiscoveryService


def make_channel(channels_dir, dir_name="test-channel", config=None, with_ui=True, with_class=True):
    """Create a channel directory structure on disk."""
    channel_dir = channels_dir / dir_name
    channel_dir.mkdir(parents=True)

    if config is None:
        config = {
            "id": dir_name,
            "name": "Test Channel",
            "description": "A test channel",
            "version": "1.0.0",
            "schemaVersion": "2.1",
            "ui": [
                {
                    "type": "settings",
                    "moduleUrl": "./settings.js",
                    "styleUrl": "./settings.css",
                }
            ],
        }
    (channel_dir / "config.json").write_text(json.dumps(config))

    if with_ui:
        ui_dir = channel_dir / "ui"
        ui_dir.mkdir()
        (ui_dir / "settings.js").write_text("// settings module")
        (ui_dir / "settings.css").write_text("/* settings styles */")

    if with_class:
        (channel_dir / "channel.py").write_text(
            "class TestChannel:\n"
            "    def __init__(self, channel_path):\n"
            "        self.channel_path = channel_path\n"
            "\n"
            "ChannelClass = TestChannel\n"
        )

    return channel_dir


@pytest.fixture()
def channels_dir(tmp_path):
    path = tmp_path / "channels"
    path.mkdir()
    return path


@pytest.fixture()
def service(channels_dir):
    return ChannelDiscoveryService(channels_dir=str(channels_dir))


@pytest.mark.unit
@pytest.mark.channels
class TestSriHash:
    def test_compute_sri_hash(self, service, tmp_path):
        content = b"test content"
        file_path = tmp_path / "file.js"
        file_path.write_bytes(content)

        expected = "sha384-" + base64.b64encode(hashlib.sha384(content).digest()).decode("ascii")
        assert service.compute_sri_hash(file_path) == expected

    def test_compute_sri_hash_missing_file(self, service, tmp_path):
        assert service.compute_sri_hash(tmp_path / "missing.js") == ""

    @pytest.mark.parametrize("content", [b"", b"short", b"a" * 10000])
    def test_sri_hash_format(self, service, tmp_path, content):
        file_path = tmp_path / "file.bin"
        file_path.write_bytes(content)

        result = service.compute_sri_hash(file_path)
        assert result.startswith("sha384-")
        # sha384 digest is 48 bytes -> 64 base64 chars
        assert len(result) == len("sha384-") + 64


@pytest.mark.unit
@pytest.mark.channels
class TestLoadChannelConfig:
    def test_valid_config(self, service, channels_dir):
        channel_dir = make_channel(channels_dir)

        config = service.load_channel_config(channel_dir)

        assert config is not None
        assert config["name"] == "Test Channel"
        assert config["schemaVersion"] == "2.1"

    def test_missing_config_file(self, service, channels_dir):
        empty_dir = channels_dir / "empty"
        empty_dir.mkdir()

        assert service.load_channel_config(empty_dir) is None

    def test_invalid_json(self, service, channels_dir):
        channel_dir = channels_dir / "broken"
        channel_dir.mkdir()
        (channel_dir / "config.json").write_text("not valid json {")

        assert service.load_channel_config(channel_dir) is None

    def test_missing_required_fields(self, service, channels_dir):
        channel_dir = make_channel(
            channels_dir,
            dir_name="incomplete",
            config={"name": "Only A Name"},
            with_ui=False,
            with_class=False,
        )

        assert service.load_channel_config(channel_dir) is None

    def test_schema_version_defaulted(self, service, channels_dir):
        channel_dir = make_channel(
            channels_dir,
            dir_name="no-schema",
            config={"name": "N", "description": "D", "version": "1.0.0"},
            with_ui=False,
            with_class=False,
        )

        config = service.load_channel_config(channel_dir)
        assert config["schemaVersion"] == "2.1"

    def test_integrity_hashes_added_for_ui_files(self, service, channels_dir):
        channel_dir = make_channel(channels_dir)

        config = service.load_channel_config(channel_dir)

        integrity = config["ui"][0]["integrity"]
        assert integrity["module"].startswith("sha384-")
        assert integrity["style"].startswith("sha384-")

    def test_integrity_not_added_for_missing_ui_files(self, service, channels_dir):
        channel_dir = make_channel(channels_dir, dir_name="no-ui-files", with_ui=False)

        config = service.load_channel_config(channel_dir)

        assert "integrity" not in config["ui"][0]


@pytest.mark.unit
@pytest.mark.channels
class TestLoadChannelClass:
    def test_loads_channel_class_export(self, service, channels_dir):
        channel_dir = make_channel(channels_dir)

        instance = service.load_channel_class(channel_dir)

        assert instance is not None
        assert instance.channel_path == str(channel_dir)

    def test_missing_channel_py(self, service, channels_dir):
        channel_dir = make_channel(channels_dir, dir_name="no-code", with_class=False)

        assert service.load_channel_class(channel_dir) is None


@pytest.mark.unit
@pytest.mark.channels
class TestDiscoverChannels:
    def test_nonexistent_directory_is_created(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        service = ChannelDiscoveryService(channels_dir=str(missing))

        result = service.discover_channels(FastAPI())

        assert result == []
        assert missing.exists()

    def test_empty_directory(self, service):
        assert service.discover_channels(FastAPI()) == []

    def test_discovers_valid_channel(self, service, channels_dir):
        make_channel(channels_dir)

        result = service.discover_channels(FastAPI())

        assert len(result) == 1
        assert result[0]["id"] == "test-channel"
        assert result[0]["instance"] is not None
        assert "test-channel" in service.loaded_channels

    def test_config_id_overrides_directory_name(self, service, channels_dir):
        make_channel(
            channels_dir,
            dir_name="dir-name",
            config={
                "id": "com.example.custom",
                "name": "N",
                "description": "D",
                "version": "1.0.0",
            },
            with_class=False,
        )

        result = service.discover_channels(FastAPI())

        assert result[0]["id"] == "com.example.custom"
        assert result[0]["directory_name"] == "dir-name"

    def test_skips_invalid_and_non_channel_entries(self, service, channels_dir):
        make_channel(channels_dir)  # the only valid one
        make_channel(channels_dir, dir_name="invalid", config={"name": "x"}, with_ui=False, with_class=False)
        (channels_dir / ".hidden").mkdir()
        (channels_dir / "assets").mkdir()  # in the well-known skip list
        (channels_dir / "stray-file.txt").write_text("not a channel")

        result = service.discover_channels(FastAPI())

        assert [c["id"] for c in result] == ["test-channel"]

    def test_static_ui_mount_registered(self, service, channels_dir):
        make_channel(channels_dir)

        service.discover_channels(FastAPI())

        assert service.static_mounts["test-channel-ui"] == "/api/channels/test-channel/ui"


@pytest.mark.unit
@pytest.mark.channels
class TestChannelAccessors:
    @pytest.fixture()
    def discovered(self, service, channels_dir):
        make_channel(channels_dir)
        service.discover_channels(FastAPI())
        return service

    def test_get_channel_instance(self, discovered):
        assert discovered.get_channel_instance("test-channel") is not None
        assert discovered.get_channel_instance("missing") is None

    def test_get_channel_config(self, discovered):
        config = discovered.get_channel_config("test-channel")
        assert config["name"] == "Test Channel"
        assert discovered.get_channel_config("missing") is None

    def test_get_all_channels(self, discovered):
        channels = discovered.get_all_channels()
        assert len(channels) == 1
        assert channels[0]["id"] == "test-channel"

    def test_update_channel_settings(self, discovered):
        assert discovered.update_channel_settings("test-channel", {"a": 1}) is True
        assert discovered.update_channel_settings("missing", {"a": 1}) is False

    def test_get_channels_manifest(self, discovered):
        manifest = discovered.get_channels_manifest()

        assert manifest["totalChannels"] == 1
        entry = manifest["channels"][0]
        assert entry["id"] == "test-channel"
        assert entry["name"] == "Test Channel"
        assert entry["schemaVersion"] == "2.1"
