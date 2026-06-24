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

"""Service for persisting distributed display images for admin UI access.

Responsibilities:
- Optionally download/copy the distributed image into a managed media directory
- Generate a lightweight thumbnail (JPEG) for fast UI rendering
- Insert a DisplaySceneImage row (with retention pruning)
- Provide helper queries for last image per display+scene

Design notes:
- We defer adding this to migrations until model addition is deployed.
- Network download is simple: stream with requests. If the URL appears local/already served, we may skip downloading.
- Hashing uses SHA256 over the binary for dedupe; if duplicate for same display+scene and hash unchanged we can skip insert (or still insert for history—configurable).
"""
from __future__ import annotations

import errno
import hashlib
import io
import logging
import tempfile
import uuid
from pathlib import Path

import requests
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DisplaySceneImage

logger = logging.getLogger(__name__)


class DisplayImagePersistenceService:
    def __init__(self, db: Session, media_root: Path | None = None):
        if media_root is None:
            root = getattr(settings, "display_images_directory", "display_images")
            media_root = Path(root)
            if not media_root.is_absolute():
                # Resolve relative directory under configured upload_dir root
                try:
                    upload_base = Path(getattr(settings, "upload_dir", ".")).resolve()
                except Exception:  # noqa: BLE001
                    upload_base = Path.cwd()
                media_root = (upload_base / media_root).resolve()
        self.db = db
        self.media_root = media_root
        self.thumb_max_width = 240
        self.thumb_max_height = 180
        self.read_only_mode = False
        try:
            self.media_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:  # Handle read-only filesystems gracefully
            if e.errno in (errno.EROFS, errno.EACCES, errno.EPERM):
                # Fallback to temp dir (ephemeral) so GET routes don't 500.
                fallback = Path(tempfile.gettempdir()) / "mimir_display_images"
                try:
                    fallback.mkdir(parents=True, exist_ok=True)
                    logger.warning(
                        "display.images.read_only root=%s errno=%s fallback=%s (metadata only mode)",
                        self.media_root,
                        e.errno,
                        fallback,
                    )
                    self.media_root = fallback
                    self.read_only_mode = True
                except Exception as inner:  # noqa: BLE001
                    # As a last resort keep read_only_mode True, disable local copy/thumbnail
                    logger.error(
                        "display.images.fallback_failed root=%s errno=%s err=%s (operating metadata-only)",
                        self.media_root,
                        e.errno,
                        inner,
                    )
                    self.read_only_mode = True
            else:
                raise

    def store_distribution_image(
        self,
        *,
        display_id: str,
        scene_id: str,
        subchannel_id: str | None,
        assignment_id: str,
        image_url: str,
        local_source_path: str | None = None,
        width: int | None = None,
        height: int | None = None,
        image_format: str | None = None,
        source: str = "distribution",
        retain_history: bool = True,
        dedupe_by_hash: bool = True,
    ) -> DisplaySceneImage:
        """Persist image metadata (and optionally a local copy + thumbnail).

        Returns the created DisplaySceneImage row.
        """
        logger.debug(
            "persist.image start display=%s scene=%s subchannel=%s url=%s",
            display_id,
            scene_id,
            subchannel_id,
            image_url,
        )

        binary: bytes | None = None
        local_path: Path | None = None
        thumb_path: Path | None = None
        sha256_hash: str | None = None
        source_path = Path(local_source_path).resolve() if local_source_path else None

        try:
            # Prefer an already-written local file to avoid blocking the API on a self-HTTP fetch.
            if source_path and source_path.exists():
                binary = source_path.read_bytes()
                sha256_hash = hashlib.sha256(binary).hexdigest()

                if dedupe_by_hash:
                    existing = (
                        self.db.query(DisplaySceneImage)
                        .filter(
                            DisplaySceneImage.display_id == display_id,
                            DisplaySceneImage.scene_id == scene_id,
                            DisplaySceneImage.subchannel_id == subchannel_id,
                            DisplaySceneImage.hash == sha256_hash,
                        )
                        .order_by(DisplaySceneImage.created_at.desc())
                        .first()
                    )
                    if existing and not retain_history:
                        logger.debug("persist.image dedupe hit existing id=%s", existing.id)
                        return existing

                rel_dir = Path(scene_id) / display_id
                abs_dir = self.media_root / rel_dir
                abs_dir.mkdir(parents=True, exist_ok=True)
                ext = source_path.suffix or ".jpg"
                filename = f"{uuid.uuid4().hex}{ext}"
                local_path = abs_dir / filename
                with open(local_path, "wb") as f:
                    f.write(binary)

                if width is None or height is None or image_format is None:
                    try:
                        with Image.open(io.BytesIO(binary)) as im:
                            width = width or im.width
                            height = height or im.height
                            image_format = image_format or (im.format.lower() if im.format else None)
                    except Exception:  # noqa: BLE001
                        pass

                try:
                    with Image.open(io.BytesIO(binary)) as im:
                        im.thumbnail((self.thumb_max_width, self.thumb_max_height))
                        thumb_filename = f"{local_path.stem}.thumb.jpg"
                        thumb_path = local_path.parent / thumb_filename
                        im.convert("RGB").save(thumb_path, "JPEG", quality=75, optimize=True)
                except Exception as e:  # noqa: BLE001
                    logger.debug("persist.image thumb generation failed: %s", e)

            # Decide whether to download: if URL already points to our public base, we might skip
            public_base = getattr(settings, "public_base_url", "")
            needs_download = True
            if public_base and image_url.startswith(public_base):
                needs_download = False

            if binary is None and needs_download and not self.read_only_mode:
                resp = requests.get(image_url, timeout=15)
                resp.raise_for_status()
                binary = resp.content
                sha256_hash = hashlib.sha256(binary).hexdigest()

                # Dedupe: if existing row with same hash for this display+scene+subchannel, skip storing new copy
                if dedupe_by_hash:
                    existing = (
                        self.db.query(DisplaySceneImage)
                        .filter(
                            DisplaySceneImage.display_id == display_id,
                            DisplaySceneImage.scene_id == scene_id,
                            DisplaySceneImage.subchannel_id == subchannel_id,
                            DisplaySceneImage.hash == sha256_hash,
                        )
                        .order_by(DisplaySceneImage.created_at.desc())
                        .first()
                    )
                    if existing and not retain_history:
                        logger.debug("persist.image dedupe hit existing id=%s", existing.id)
                        return existing

                # Store binary
                rel_dir = Path(scene_id) / display_id
                abs_dir = self.media_root / rel_dir
                abs_dir.mkdir(parents=True, exist_ok=True)
                ext = ".jpg"
                filename = f"{uuid.uuid4().hex}{ext}"
                local_path = abs_dir / filename
                with open(local_path, "wb") as f:
                    f.write(binary)

                # Attempt derive metadata via Pillow
                if width is None or height is None or image_format is None:
                    try:
                        with Image.open(io.BytesIO(binary)) as im:
                            width = width or im.width
                            height = height or im.height
                            image_format = image_format or (im.format.lower() if im.format else None)
                    except Exception:  # noqa: BLE001
                        pass

                # Create thumbnail
                try:
                    with Image.open(io.BytesIO(binary)) as im:
                        im.thumbnail((self.thumb_max_width, self.thumb_max_height))
                        thumb_filename = f"{local_path.stem}.thumb.jpg"
                        thumb_path = local_path.parent / thumb_filename
                        im.convert("RGB").save(thumb_path, "JPEG", quality=75, optimize=True)
                except Exception as e:  # noqa: BLE001
                    logger.debug("persist.image thumb generation failed: %s", e)
            elif binary is None and needs_download and self.read_only_mode:
                # We are in metadata-only mode: skip downloading to disk, but optionally hash
                try:
                    resp = requests.get(image_url, timeout=10)
                    resp.raise_for_status()
                    binary = resp.content
                    sha256_hash = hashlib.sha256(binary).hexdigest()
                except Exception:  # noqa: BLE001
                    pass  # Non-fatal; continue storing reference
            elif binary is None:
                # We trust provided image_url; not downloading
                logger.debug("persist.image skipping download (public base match)")

            row = DisplaySceneImage(
                id=str(uuid.uuid4()),
                display_id=display_id,
                scene_id=scene_id,
                subchannel_id=subchannel_id,
                assignment_id=assignment_id,
                image_url=image_url,
                stored_local_path=str(local_path) if local_path else None,
                thumbnail_path=str(thumb_path) if thumb_path else None,
                width=width,
                height=height,
                format=image_format,
                hash=sha256_hash,
                source=source,
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)

            logger.info(
                "persist.image stored id=%s display=%s scene=%s subchannel=%s local=%s thumb=%s",
                row.id,
                display_id,
                scene_id,
                subchannel_id,
                bool(local_path),
                bool(thumb_path),
            )
            return row
        except Exception as e:  # noqa: BLE001
            logger.error("persist.image failure display=%s scene=%s error=%s", display_id, scene_id, e)
            raise

    def get_last_for_display_scene(
        self, display_id: str, scene_id: str, subchannel_id: str | None = None
    ) -> DisplaySceneImage | None:
        q = self.db.query(DisplaySceneImage).filter(
            DisplaySceneImage.display_id == display_id,
            DisplaySceneImage.scene_id == scene_id,
        )
        if subchannel_id is not None:
            q = q.filter(DisplaySceneImage.subchannel_id == subchannel_id)
        return q.order_by(DisplaySceneImage.created_at.desc()).first()

    def prune_retention(self, max_per_pair: int = 10) -> int:
        """Keep only the newest N images per (display_id, scene_id, subchannel_id)."""
        # This is a simplified in-Python version; for large scale, move to SQL window function
        rows = self.db.query(DisplaySceneImage).order_by(DisplaySceneImage.created_at.desc()).all()
        seen = {}
        to_delete = []
        for r in rows:
            key = (r.display_id, r.scene_id, r.subchannel_id)
            count = seen.get(key, 0)
            if count >= max_per_pair:
                to_delete.append(r)
            else:
                seen[key] = count + 1
        for r in to_delete:
            try:
                self.db.delete(r)
            except Exception:  # noqa: BLE001
                # Non-critical; continue attempting deletions
                pass
        if to_delete:
            self.db.commit()
        return len(to_delete)
