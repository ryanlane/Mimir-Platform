# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
File Sources service.

Gives the platform (and every channel plugin) a uniform way to browse and
read media from operator-configured roots:

  * "local"  — a subpath of the single generic bind mount /mnt/host-media
               (override with MIMIR_HOST_MEDIA_MOUNT). The operator mounts a
               broad parent once in docker-compose; named sources are carved
               out beneath it entirely from the web UI.
  * "smb"    — an SMB/CIFS share reached in userspace via smbprotocol's
               smbclient API. No host mounts or privileged containers; the
               share address and credentials are entered in the web UI.

Plugins reference files as ``source://<source_id>/<relative/path>`` and call
``localize()`` to turn a reference into a real local filesystem path. Local
sources resolve in place; SMB files are copied into a server-side cache on
first use (frame extractors like OpenCV need a seekable local file).
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from app.db.models import FileSource

logger = logging.getLogger(__name__)

HOST_MEDIA_MOUNT = Path(os.environ.get("MIMIR_HOST_MEDIA_MOUNT", "/mnt/host-media"))
SMB_CACHE_DIR = Path(os.environ.get(
    "MIMIR_SMB_CACHE_DIR", "/var/opt/mimir/mimir-api/uploads/source-cache"))

SOURCE_REF_PREFIX = "source://"


class FileSourceError(Exception):
    """Raised for invalid paths, unreachable shares, or misconfigured sources."""


@dataclass
class Entry:
    name: str
    path: str  # relative to source root, POSIX-style
    is_dir: bool
    size: int = 0


@dataclass
class Listing:
    path: str
    breadcrumbs: list[dict[str, str]] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reference helpers

def make_ref(source_id: str, rel_path: str) -> str:
    return f"{SOURCE_REF_PREFIX}{source_id}/{rel_path.lstrip('/')}"


def parse_ref(ref: str) -> tuple[str, str]:
    """Split ``source://<id>/<rel path>`` -> (source_id, rel_path)."""
    if not ref.startswith(SOURCE_REF_PREFIX):
        raise FileSourceError(f"Not a source reference: {ref}")
    rest = ref[len(SOURCE_REF_PREFIX):]
    source_id, _, rel_path = rest.partition("/")
    if not source_id:
        raise FileSourceError(f"Malformed source reference: {ref}")
    return source_id, rel_path


def is_ref(value: str) -> bool:
    return isinstance(value, str) and value.startswith(SOURCE_REF_PREFIX)


# ---------------------------------------------------------------------------
# Path safety

def _clean_rel(rel_path: str) -> PurePosixPath:
    """Normalise a client-supplied relative path, refusing traversal."""
    p = PurePosixPath(rel_path.strip().lstrip("/"))
    if ".." in p.parts:
        raise FileSourceError(f"Path traversal rejected: {rel_path}")
    return p


def _breadcrumbs(rel: PurePosixPath) -> list[dict[str, str]]:
    crumbs = [{"name": "", "path": ""}]
    acc = PurePosixPath("")
    for part in rel.parts:
        acc = acc / part
        crumbs.append({"name": part, "path": str(acc)})
    return crumbs


# ---------------------------------------------------------------------------
# Local sources

def _local_root(source: FileSource) -> Path:
    sub = (source.config or {}).get("path", "").strip().lstrip("/")
    root = (HOST_MEDIA_MOUNT / sub).resolve() if sub else HOST_MEDIA_MOUNT.resolve()
    mount = HOST_MEDIA_MOUNT.resolve()
    if root != mount and mount not in root.parents:
        raise FileSourceError(
            f"Local source path escapes the host media mount: {sub}")
    return root


def _browse_local(source: FileSource, rel: PurePosixPath,
                  extensions: set[str] | None) -> Listing:
    root = _local_root(source)
    target = (root / rel).resolve()
    if root != target and root not in target.parents:
        raise FileSourceError("Path traversal rejected")
    if not target.is_dir():
        raise FileSourceError(f"Not a directory: {rel}")

    entries: list[Entry] = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            entries.append(Entry(child.name, str(rel / child.name), True))
        elif extensions is None or child.suffix.lower() in extensions:
            try:
                size = child.stat().st_size
            except OSError:
                size = 0
            entries.append(Entry(child.name, str(rel / child.name), False, size))
    return Listing(str(rel) if rel.parts else "", _breadcrumbs(rel), entries)


# ---------------------------------------------------------------------------
# SMB sources (userspace via smbprotocol)

def _smb_conn(source: FileSource) -> dict[str, Any]:
    cfg = source.config or {}
    host, share = cfg.get("host", "").strip(), cfg.get("share", "").strip()
    if not host or not share:
        raise FileSourceError("SMB source needs 'host' and 'share'")
    root = cfg.get("root_path", "").strip().strip("/").replace("/", "\\")
    base = rf"\\{host}\{share}"
    if root:
        base = rf"{base}\{root}"
    return {
        "base": base,
        "kwargs": {
            "username": cfg.get("username") or None,
            "password": cfg.get("password") or None,
            "port": int(cfg.get("port") or 445),
        },
    }


def _browse_smb(source: FileSource, rel: PurePosixPath,
                extensions: set[str] | None) -> Listing:
    import smbclient  # deferred: smbprotocol is only needed when SMB is used

    conn = _smb_conn(source)
    unc = conn["base"] + ("".join("\\" + p for p in rel.parts))
    entries: list[Entry] = []
    try:
        with smbclient.scandir(unc, **conn["kwargs"]) as it:
            listing = sorted(it, key=lambda e: (not e.is_dir(), e.name.lower()))
    except Exception as exc:
        raise FileSourceError(f"SMB browse failed: {exc}") from exc

    for item in listing:
        if item.name.startswith("."):
            continue
        child_rel = str(rel / item.name)
        if item.is_dir():
            entries.append(Entry(item.name, child_rel, True))
        elif extensions is None or PurePosixPath(item.name).suffix.lower() in extensions:
            try:
                size = item.stat().st_size
            except Exception:
                size = 0
            entries.append(Entry(item.name, child_rel, False, size))
    return Listing(str(rel) if rel.parts else "", _breadcrumbs(rel), entries)


# ---------------------------------------------------------------------------
# Public API

def browse(source: FileSource, rel_path: str = "",
           extensions: list[str] | None = None) -> Listing:
    """List one directory of a source. ``extensions`` filters files (dirs
    always shown) and is matched case-insensitively with the leading dot."""
    rel = _clean_rel(rel_path)
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}"
            for e in extensions} if extensions else None
    if source.type == "local":
        return _browse_local(source, rel, exts)
    if source.type == "smb":
        return _browse_smb(source, rel, exts)
    raise FileSourceError(f"Unknown source type: {source.type}")


def localize(source: FileSource, rel_path: str) -> Path:
    """Return a real local filesystem path for a file within a source.

    Local sources resolve in place (no copy). SMB files are downloaded into
    SMB_CACHE_DIR once and reused; the cache key includes source id and path
    so re-adding the same file is free.
    """
    rel = _clean_rel(rel_path)
    if source.type == "local":
        root = _local_root(source)
        target = (root / rel).resolve()
        if root != target and root not in target.parents:
            raise FileSourceError("Path traversal rejected")
        if not target.is_file():
            raise FileSourceError(f"File not found: {rel}")
        return target

    if source.type == "smb":
        import smbclient

        key = hashlib.sha256(f"{source.id}:{rel}".encode()).hexdigest()[:24]
        cached = SMB_CACHE_DIR / f"{key}{PurePosixPath(rel).suffix.lower()}"
        if cached.is_file() and cached.stat().st_size > 0:
            return cached
        SMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        conn = _smb_conn(source)
        unc = conn["base"] + "".join("\\" + p for p in rel.parts)
        tmp = cached.with_suffix(cached.suffix + ".part")
        try:
            with smbclient.open_file(unc, mode="rb", **conn["kwargs"]) as src, \
                    open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
            tmp.rename(cached)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            raise FileSourceError(f"SMB fetch failed: {exc}") from exc
        logger.info("[FileSources] cached %s -> %s (%d bytes)",
                    rel, cached, cached.stat().st_size)
        return cached

    raise FileSourceError(f"Unknown source type: {source.type}")


def test_source(source: FileSource) -> tuple[bool, str]:
    """Cheap reachability check used by the Settings UI."""
    try:
        listing = browse(source, "")
        return True, f"OK — {len(listing.entries)} entries at root"
    except FileSourceError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"Unexpected error: {exc}"


def redact_config(source_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets before a config leaves the API."""
    cfg = dict(config or {})
    if source_type == "smb":
        cfg["has_password"] = bool(cfg.pop("password", None))
    return cfg
