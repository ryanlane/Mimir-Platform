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

"""Image Swap Storage Utility

Purpose:
- Provide a centralized helper for writing ephemeral per-display image files that are then
  served via the /media mount (see main.py) rather than embedding base64 or indirect
  in-memory IDs in MQTT payloads.
- Each distribution event writes one file per display so displays can fetch independently.
- Filenames incorporate scene, display, channel/subchannel (if present), and a UUID + epoch
  to avoid collisions while still being traceable for debugging.

Directory Layout (under configured display_images_directory root):
  swap/<scene_id>/<display_id>/<scene_epoch?>/<file>
We keep it simple initially:
  swap/<scene_id>/<display_id>/<uuid>.<ext>

Retention:
- A lightweight cleanup helper can prune oldest files beyond a per-display cap.
  (Scheduler worker will call prune_swap if configured.)

Config Reuse:
- Uses settings.display_images_directory; resolves relative path same as persistence service.

Return Value:
- Function save_swap_image returns a tuple (file_path, public_url, bytes_written)

Thread/Async Safety:
- File writes are synchronous (fast for single images). Caller can offload if needed.

"""
from __future__ import annotations

import errno
import logging
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Public constant for swap root folder name (beneath media root)
SWAP_DIR_NAME = "swap"


def _resolve_media_root() -> Path:
    raw = getattr(settings, "display_images_directory", "display_images")
    root = Path(raw)
    if not root.is_absolute():
        try:
            upload_base = Path(getattr(settings, "upload_dir", ".")).resolve()
        except Exception:  # noqa: BLE001
            upload_base = Path.cwd()
        root = (upload_base / root).resolve()
    return root


def ensure_swap_dir(scene_id: str, display_id: str) -> Path:
    base = _resolve_media_root() / SWAP_DIR_NAME / scene_id / display_id
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as e:  # handle read-only gracefully
        if e.errno in (errno.EROFS, errno.EACCES, errno.EPERM):
            logger.warning("image.swap.read_only dir=%s errno=%s", base, e.errno)
        else:
            raise
    return base


def save_swap_image(
    *,
    scene_id: str,
    display_id: str,
    image_bytes: bytes,
    content_type: str | None,
    public_base_url: str | None = None,
) -> tuple[Path | None, str | None, int]:
    """Write bytes to per-display swap directory.

    Args:
        scene_id: Scene identifier
        display_id: Display identifier (hostname or unique ID)
        image_bytes: Binary image data
        content_type: MIME type (used to choose extension when possible)

    Returns:
        (file_path, public_url, bytes_written) with None entries on failure.
    """
    try:
        target_dir = ensure_swap_dir(scene_id, display_id)
        # Determine extension
        ext = ".jpg"
        if content_type:
            if "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "jpeg" in content_type or "jpg" in content_type:
                ext = ".jpg"
            elif "webp" in content_type:
                ext = ".webp"
        fname = f"{uuid.uuid4().hex}{ext}"
        path = target_dir / fname
        with open(path, "wb") as f:
            f.write(image_bytes)
        # Build public URL: /media/<relative-from-media-root>
        media_root = _resolve_media_root()
        rel = path.relative_to(media_root)
        public_root = (public_base_url or settings.public_base_url).rstrip("/")
        public_url = f"{public_root}/media/{rel.as_posix()}"
        logger.debug("image.swap.saved scene=%s display=%s bytes=%d path=%s", scene_id, display_id, len(image_bytes), path)
        return path, public_url, len(image_bytes)
    except Exception as e:  # noqa: BLE001
        logger.error("image.swap.save_failed scene=%s display=%s err=%s", scene_id, display_id, e)
        return None, None, 0


def prune_swap(*, max_files_per_display: int = 20, max_total_per_scene: int | None = None) -> int:
    """Prune oldest files keeping only the newest N per (scene, display) pair.

    Args:
        max_files_per_display: Cap per display directory
        max_total_per_scene: Optional cap across all displays in a scene (best-effort)

    Returns:
        Total files deleted.
    """
    deleted = 0
    root = _resolve_media_root() / SWAP_DIR_NAME
    if not root.exists():
        return 0
    try:
        # Iterate scenes
        for scene_dir in root.iterdir():
            if not scene_dir.is_dir():
                continue
            scene_file_count: int = 0
            scene_all_files: list[Path] = []
            for display_dir in scene_dir.iterdir():
                if not display_dir.is_dir():
                    continue
                files = [p for p in display_dir.iterdir() if p.is_file()]
                files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                scene_file_count += len(files)
                scene_all_files.extend(files)
                if len(files) > max_files_per_display:
                    for old in files[max_files_per_display:]:
                        try:
                            old.unlink()
                            deleted += 1
                        except Exception:  # noqa: BLE001
                            continue
            if max_total_per_scene and scene_file_count > max_total_per_scene:
                scene_all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                overflow = scene_file_count - max_total_per_scene
                for old in scene_all_files[max_total_per_scene: max_total_per_scene + overflow]:
                    try:
                        old.unlink()
                        deleted += 1
                    except Exception:  # noqa: BLE001
                        continue
    except Exception as e:  # noqa: BLE001
        logger.debug("image.swap.prune_error err=%s", e)
    if deleted:
        logger.info("image.swap.prune deleted=%d", deleted)
    return deleted


def swap_summary() -> dict:
    """Return aggregate statistics about swap storage.

    Structure:
        {
          'scenes': <count>, 'displays': <count>, 'files': <count>,
          'total_bytes': <int>, 'per_scene': { scene_id: { 'displays': int, 'files': int, 'bytes': int } }
        }
    """
    root = _resolve_media_root() / SWAP_DIR_NAME
    if not root.exists():
        return {"scenes": 0, "displays": 0, "files": 0, "total_bytes": 0, "per_scene": {}}
    per_scene: dict[str, dict] = {}
    total_files = 0
    total_bytes = 0
    display_ids: set[str] = set()
    for scene_dir in root.iterdir():
        if not scene_dir.is_dir():
            continue
        scene_id = scene_dir.name
        sc_files = 0
        sc_bytes = 0
        sc_display_ids: set[str] = set()
        for display_dir in scene_dir.iterdir():
            if not display_dir.is_dir():
                continue
            disp_id = display_dir.name
            sc_display_ids.add(disp_id)
            display_ids.add(disp_id)
            for f in display_dir.iterdir():
                if f.is_file():
                    sc_files += 1
                    total_files += 1
                    try:
                        size = f.stat().st_size
                    except OSError:
                        size = 0
                    sc_bytes += size
                    total_bytes += size
        per_scene[scene_id] = {
            "displays": len(sc_display_ids),
            "files": sc_files,
            "bytes": sc_bytes,
        }
    return {
        "scenes": len(per_scene),
        "displays": len(display_ids),
        "files": total_files,
        "total_bytes": total_bytes,
        "per_scene": per_scene,
    }


def list_scene_swap(scene_id: str) -> dict:
    """List swap files for a specific scene grouped by display."""
    root = _resolve_media_root() / SWAP_DIR_NAME / scene_id
    if not root.exists() or not root.is_dir():
        return {"scene_id": scene_id, "displays": {}, "files": 0}
    result: dict[str, list] = {}
    total = 0
    for display_dir in root.iterdir():
        if not display_dir.is_dir():
            continue
        files_list = []
        for f in display_dir.iterdir():
            if f.is_file():
                try:
                    stat = f.stat()
                    files_list.append({
                        "name": f.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "url": f"{settings.public_base_url}/media/{SWAP_DIR_NAME}/{scene_id}/{display_dir.name}/{f.name}",
                    })
                    total += 1
                except OSError:
                    continue
        files_list.sort(key=lambda x: x["mtime"], reverse=True)
        result[display_dir.name] = files_list
    return {"scene_id": scene_id, "displays": result, "files": total}
