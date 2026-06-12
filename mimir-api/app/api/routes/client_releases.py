"""Client release cache endpoints (Phase 2).

The production server caches the pinned mimir-display release artifact
locally (downloaded by mimir-update.sh into CLIENT_RELEASES_DIR) so display
clients can fetch updates from the LAN without internet access.

Layout on disk (one subdirectory per version):

    <client_releases_dir>/
      v1.0.3/
        manifest.json                  # version, artifact, sha256, min_server_version
        mimir_display-1.0.3.tar.gz

    latest -> v1.0.3                   # symlink maintained by mimir-update.sh

Endpoints:
    GET /api/client-releases/latest             -> manifest + download path
    GET /api/client-releases/{version}/download -> artifact file
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(prefix="/client-releases", tags=["client-releases"])


def _releases_dir() -> Path:
    return Path(
        getattr(settings, "client_releases_dir", None)
        or "/var/opt/mimir/mimir-api/client-releases"
    )


def _load_manifest(version_dir: Path) -> dict:
    manifest_path = version_dir / "manifest.json"
    if not manifest_path.is_file():
        raise HTTPException(status_code=404, detail="release manifest not found")
    try:
        return json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"invalid release manifest: {exc}") from exc


@router.get("/latest")
async def get_latest_client_release():
    """Return the manifest of the newest cached client release.

    Display clients poll this to learn the desired version; the manifest's
    sha256 lets them verify the artifact after download.
    """
    base = _releases_dir()
    latest = base / "latest"
    if not latest.exists():
        raise HTTPException(status_code=404, detail="no client release cached on this server")
    version_dir = latest.resolve()
    manifest = _load_manifest(version_dir)
    version = manifest.get("version") or version_dir.name.lstrip("v")
    return {
        **manifest,
        "download_path": f"/api/client-releases/v{version}/download",
    }


@router.get("/{version}/download")
async def download_client_release(version: str):
    """Serve the cached artifact for a specific version (e.g. 'v1.0.3')."""
    safe = version.strip("/").replace("..", "")
    version_dir = (_releases_dir() / safe).resolve()
    if not version_dir.is_dir() or _releases_dir().resolve() not in version_dir.parents:
        raise HTTPException(status_code=404, detail="release not found")
    manifest = _load_manifest(version_dir)
    artifact = manifest.get("artifact")
    if not artifact:
        raise HTTPException(status_code=500, detail="manifest missing artifact name")
    artifact_path = version_dir / artifact
    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="artifact file missing")
    return FileResponse(
        artifact_path,
        media_type="application/gzip",
        filename=artifact,
        headers={"X-Artifact-Sha256": manifest.get("sha256", "")},
    )
