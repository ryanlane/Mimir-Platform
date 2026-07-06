"""Tests for the debug CORS origin regex used by self-hosted LAN setups."""

import re

from app.main import _dev_lan_origin_regex
from app.config import settings


def test_dev_lan_origin_regex_allows_mdns_hostname(monkeypatch):
    """mDNS hostnames like mimir.local should be accepted in debug mode."""
    monkeypatch.setattr(settings, "debug", True)

    pattern = _dev_lan_origin_regex()

    assert pattern is not None
    assert re.match(pattern, "http://mimir.local:8080")


def test_dev_lan_origin_regex_rejects_unrelated_public_hostname(monkeypatch):
    """Public hostnames should still require explicit CORS configuration."""
    monkeypatch.setattr(settings, "debug", True)

    pattern = _dev_lan_origin_regex()

    assert pattern is not None
    assert re.match(pattern, "http://example.com:8080") is None
