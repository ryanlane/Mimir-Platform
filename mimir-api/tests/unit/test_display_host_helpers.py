import socket

import pytest

from app.api.routes.displays._helpers import (
    _host_resolves_to_private_network,
    _normalize_public_host_hint,
)


def _fail_getaddrinfo(*args, **kwargs):
    raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")


def test_mdns_host_accepted_without_server_side_resolution(monkeypatch):
    # The server often cannot resolve .local names even though the browser
    # that supplied the hint can; .local must not require getaddrinfo.
    monkeypatch.setattr(socket, "getaddrinfo", _fail_getaddrinfo)
    assert _host_resolves_to_private_network("mimir.local") is True
    assert _normalize_public_host_hint("mimir.local") == "mimir.local"


def test_unresolvable_bare_hostname_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fail_getaddrinfo)
    assert _host_resolves_to_private_network("mimir-server") is False
    assert _normalize_public_host_hint("mimir-server") is None


def test_private_ip_hint_accepted():
    assert _normalize_public_host_hint("192.168.1.50") == "192.168.1.50"


def test_public_ip_hint_rejected():
    assert _normalize_public_host_hint("8.8.8.8") is None


@pytest.mark.parametrize("hint", [None, "", "   "])
def test_empty_hint_rejected(hint):
    assert _normalize_public_host_hint(hint) is None
