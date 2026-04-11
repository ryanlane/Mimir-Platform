import socket

from app.config import Settings


def test_public_base_url_prefers_primary_ipv4_over_hostname(monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "oak")
    monkeypatch.setattr(Settings, "_discover_primary_ipv4", staticmethod(lambda: "192.168.1.50"))

    settings = Settings(
        public_host=None,
        public_mdns_host=None,
        public_port=5000,
        api_port=5000,
        public_scheme="http",
    )

    assert settings.public_base_url == "http://192.168.1.50:5000"


def test_public_base_url_keeps_explicit_public_host_precedence(monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "oak")
    monkeypatch.setattr(Settings, "_discover_primary_ipv4", staticmethod(lambda: "192.168.1.50"))

    settings = Settings(
        public_host="mimir.local",
        public_mdns_host=None,
        public_port=5000,
        api_port=5000,
        public_scheme="http",
    )

    assert settings.public_base_url == "http://mimir.local:5000"