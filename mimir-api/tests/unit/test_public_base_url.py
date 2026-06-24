import socket

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def _clean_public_env(monkeypatch):
    # Settings fields are populated via env aliases (constructor kwargs are
    # ignored because of extra="ignore"), so drive everything through env.
    for var in (
        "PUBLIC_HOST", "API_PUBLIC_HOST", "EXTERNAL_HOST",
        "PUBLIC_MDNS_HOST", "API_PUBLIC_MDNS_HOST",
        "PUBLIC_PORT", "API_PUBLIC_PORT", "EXTERNAL_PORT",
        "PUBLIC_SCHEME", "API_PUBLIC_SCHEME",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "mimir-server")


def test_public_base_url_prefers_primary_ipv4_over_hostname(monkeypatch):
    monkeypatch.setattr(Settings, "_discover_primary_ipv4", staticmethod(lambda: "192.168.1.50"))

    assert Settings().public_base_url == "http://192.168.1.50:5000"


def test_public_base_url_keeps_explicit_public_host_precedence(monkeypatch):
    monkeypatch.setattr(Settings, "_discover_primary_ipv4", staticmethod(lambda: "192.168.1.50"))
    monkeypatch.setenv("PUBLIC_HOST", "mimir.local")

    assert Settings().public_base_url == "http://mimir.local:5000"


def test_public_base_url_prefers_mdns_name_over_bare_hostname(monkeypatch):
    # When IPv4 discovery fails, advertise hostname.local rather than the
    # bare hostname, which other machines cannot resolve.
    monkeypatch.setattr(Settings, "_discover_primary_ipv4", staticmethod(lambda: None))

    assert Settings().public_base_url == "http://mimir.local:5000"
