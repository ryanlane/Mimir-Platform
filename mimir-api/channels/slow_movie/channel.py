"""
Slow Movie Player Channel for Mimir Platform

Plays video files one frame at a time at ultra-slow speeds, inspired by
Bryan Boyer's Very Slow Movie Player concept. Each display update advances
the video by a configurable number of frames at a configurable time interval.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from .models import GlobalSettings, Movie, MovieDatabase
from .video_service import VideoService

_PLUGIN_DIR = Path(__file__).parent

logger = logging.getLogger("mimir.channels.slowmovie")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class SlowMovieChannel:
    """
    Slow Movie Player channel for Mimir Platform.

    Manages a library of video files and serves individual frames as images.
    One frame is advanced per request_image call, respecting quiet hours and
    per-movie timing overrides.
    """

    def __init__(self, channel_dir: str):
        self.channel_dir = Path(channel_dir)
        self.data_dir = self.channel_dir / "data"
        self.uploads_dir = self.channel_dir / "videos"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

        self._plugin_json = self.channel_dir / "plugin.json"
        self._config = self._load_config()

        self.db = MovieDatabase(self.data_dir)
        self.last_update: Optional[datetime] = None
        self.last_error: Optional[str] = None

        logger.info("[SlowMovie] Initialized channel_dir=%s", self.channel_dir)

    # -------------------------------------------------------------------------
    # Config helpers

    def _load_config(self) -> Dict[str, Any]:
        if self._plugin_json.exists():
            return json.loads(self._plugin_json.read_text())
        return {"id": "com.mimir.slowmovie", "name": "Slow Movie Player"}

    @property
    def id(self) -> str:
        return self._config.get("id", "com.mimir.slowmovie")

    # -------------------------------------------------------------------------
    # Quiet hours

    def _in_quiet_hours(self) -> bool:
        settings = self.db.get_settings()
        if not settings.use_quiet_hours:
            return False
        now_hour = datetime.now().hour
        start, end = settings.quiet_start, settings.quiet_end
        if start < end:
            return start <= now_hour < end
        # Wraps midnight
        return now_hour >= start or now_hour < end

    # -------------------------------------------------------------------------
    # Effective settings (per-movie overrides global)

    def _effective_settings(self, movie: Movie) -> Dict[str, Any]:
        gs = self.db.get_settings()
        return {
            "time_per_frame": movie.time_per_frame if movie.time_per_frame is not None else gs.time_per_frame,
            "time_per_frame_unit": movie.time_per_frame_unit or gs.time_per_frame_unit,
            "skip_frames": movie.skip_frames if movie.skip_frames is not None else gs.skip_frames,
        }

    # -------------------------------------------------------------------------
    # Core: frame advance + render

    def _next_frame_number(self, movie: Movie, skip: int) -> int:
        """Return the next frame index, wrapping at end of movie."""
        if movie.total_frames <= 0:
            return 0
        if movie.is_random:
            import random
            return random.randint(0, movie.total_frames - 1)
        return (movie.current_frame + skip) % movie.total_frames

    def _render_frame(
        self,
        movie: Movie,
        frame_number: int,
        target_size: Optional[tuple] = None,
    ) -> Optional[bytes]:
        video_path = Path(movie.video_path)
        if not video_path.exists():
            logger.error("[SlowMovie] Video file not found: %s", video_path)
            return None
        return VideoService.extract_frame(video_path, frame_number, target_size)

    # -------------------------------------------------------------------------
    # Mimir ChannelProtocol interface

    def get_manifest(self) -> Dict[str, Any]:
        movies = self.db.list_movies()
        active = self.db.get_active_movie()
        settings = self.db.get_settings()
        healthy = self.last_error is None
        ui_base = f"/api/channels/{self.id}"
        return {
            "id": self.id,
            "name": "Slow Movie Player",
            "version": self._config.get("version", "1.0.0"),
            "description": self._config.get("description", ""),
            "icon": "film",
            "capabilities": {
                "supports_upload": True,
                "video_formats": ["mp4", "avi", "mov", "mkv", "webm"],
            },
            "ui": {
                "components": {
                    "manager": f"{ui_base}/ui/manage.esm.js",
                },
                "elements": {
                    "manager": "x-slow-movie-manager",
                },
            },
            "status": self.get_status(),
            "healthy": healthy,
            "now_playing": active.to_dict() if active else None,
            "movie_count": len(movies),
            "settings": settings.to_dict(),
            "diagnostics": {
                "last_error": self.last_error,
                "last_update": self.last_update.isoformat() if self.last_update else None,
                "opencv_available": VideoService.is_available(),
            },
        }

    def get_status(self) -> Dict[str, Any]:
        active = self.db.get_active_movie()
        in_quiet = self._in_quiet_hours()
        status: Dict[str, Any] = {
            "in_quiet_hours": in_quiet,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "last_error": self.last_error,
        }
        if active:
            eff = self._effective_settings(active)
            progress_pct = round(active.current_frame / active.total_frames * 100, 1) if active.total_frames > 0 else 0.0
            status.update({
                "active_movie_id": active.id,
                "active_movie_title": active.title,
                "current_frame": active.current_frame,
                "total_frames": active.total_frames,
                "progress_pct": progress_pct,
                "time_per_frame": eff["time_per_frame"],
                "time_per_frame_unit": eff["time_per_frame_unit"],
                "skip_frames": eff["skip_frames"],
                "is_random": active.is_random,
            })
        return status

    async def request_image(self, request_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Advance the active movie by skip_frames and return the new frame as JPEG bytes.

        request_data keys (all optional):
          - movie_id: override which movie to advance
          - resolution: [width, height] to resize to
          - include_base64: bool
          - advance: bool (default True) – set False to serve current frame without advancing
        """
        try:
            data = request_data or {}
            include_base64 = bool(data.get("include_base64", False))
            should_advance = bool(data.get("advance", True))

            # Resolve target movie
            movie_id = data.get("movie_id")
            if movie_id:
                movie = self.db.get_movie(movie_id)
                if not movie:
                    return {"success": False, "error": f"Movie {movie_id} not found"}
            else:
                movie = self.db.get_active_movie()
                if not movie:
                    return {"success": False, "error": "No active movie set"}

            # Quiet hours: serve current frame without advancing
            if self._in_quiet_hours() and should_advance:
                should_advance = False

            eff = self._effective_settings(movie)
            skip = max(1, int(eff["skip_frames"]))

            # Determine frame to render
            if should_advance:
                next_frame = self._next_frame_number(movie, skip)
            else:
                next_frame = movie.current_frame

            # Resolution for resizing
            resolution = data.get("resolution")
            target_size = None
            if resolution and isinstance(resolution, (list, tuple)) and len(resolution) == 2:
                try:
                    target_size = (int(resolution[0]), int(resolution[1]))
                except (TypeError, ValueError):
                    pass

            frame_bytes = self._render_frame(movie, next_frame, target_size)

            if frame_bytes is None:
                # Try placeholder
                placeholder = self.channel_dir / "placeholder.jpg"
                if placeholder.exists():
                    frame_bytes = placeholder.read_bytes()
                else:
                    return {"success": False, "error": "Frame extraction failed and no placeholder available"}

            # Persist advance
            if should_advance:
                self.db.update_movie(movie.id, {
                    "current_frame": next_frame,
                    "last_played_at": datetime.now(timezone.utc).isoformat(),
                })

            self.last_update = datetime.now(timezone.utc)
            self.last_error = None

            response: Dict[str, Any] = {
                "success": True,
                "bytes": frame_bytes,
                "content_type": "image/jpeg",
                "movie_id": movie.id,
                "movie_title": movie.title,
                "frame_number": next_frame,
                "total_frames": movie.total_frames,
                "advanced": should_advance,
                "in_quiet_hours": self._in_quiet_hours(),
                "preferred_transport": "bytes",
            }
            if include_base64:
                response["image"] = base64.b64encode(frame_bytes).decode("utf-8")
            return response

        except Exception as exc:
            self.last_error = str(exc)
            logger.error("[SlowMovie] request_image failed: %s", exc)
            return {"success": False, "error": f"request_image failed: {exc}"}

    def get_router(self) -> APIRouter:
        router = APIRouter()

        # --- Static UI assets --------------------------------------------

        _ui_dir = _PLUGIN_DIR / "ui"

        @router.get("/ui/{filename:path}")
        async def serve_ui(filename: str):
            file_path = _ui_dir / filename
            # Resolve and guard against path traversal
            try:
                file_path = file_path.resolve()
                _ui_dir.resolve()
                file_path.relative_to(_ui_dir.resolve())
            except (ValueError, RuntimeError):
                raise HTTPException(403, "Forbidden")
            if not file_path.exists():
                raise HTTPException(404, f"UI asset not found: {filename}")
            media_type = "application/javascript" if filename.endswith(".js") else "text/css"
            return Response(content=file_path.read_bytes(), media_type=media_type,
                            headers={"Cache-Control": "no-cache"})

        # --- Status / manifest -------------------------------------------

        @router.get("/test")
        async def test():
            return JSONResponse({"success": True, "id": self.id, "message": "Slow Movie channel responsive"})

        @router.get("/status")
        async def get_status_route():
            return JSONResponse(self.get_status())

        @router.get("/manifest")
        async def get_manifest_route():
            return JSONResponse(self.get_manifest())

        # --- Settings ----------------------------------------------------

        @router.get("/settings")
        async def get_settings():
            return JSONResponse(self.db.get_settings().to_dict())

        @router.put("/settings")
        async def update_settings(request: Request):
            body = await request.json()
            updated = self.db.update_settings(body)
            return JSONResponse({"success": True, "settings": updated.to_dict()})

        # --- Movies list / add -------------------------------------------

        @router.get("/movies")
        async def list_movies():
            movies = [m.to_dict() for m in self.db.list_movies()]
            return JSONResponse({"movies": movies, "total": len(movies)})

        @router.post("/movies")
        async def add_movie_by_path(request: Request):
            body = await request.json()
            video_path_str = body.get("video_path", "").strip()
            if not video_path_str:
                raise HTTPException(400, "video_path is required")

            video_path = Path(video_path_str)
            if not video_path.exists():
                raise HTTPException(400, f"File not found: {video_path_str}")
            if video_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise HTTPException(400, f"Unsupported format: {video_path.suffix}")

            info = VideoService.get_video_info(video_path)
            movie = Movie(
                id=str(uuid.uuid4()),
                title=body.get("title") or video_path.stem,
                video_path=str(video_path),
                added_at=datetime.now(timezone.utc).isoformat(),
                **{k: info[k] for k in ("total_frames", "fps", "width", "height", "duration_seconds")},
            )
            self.db.add_movie(movie)
            return JSONResponse({"success": True, "movie": movie.to_dict()}, status_code=201)

        # --- Individual movie operations ---------------------------------

        @router.get("/movies/{movie_id}")
        async def get_movie(movie_id: str):
            movie = self.db.get_movie(movie_id)
            if not movie:
                raise HTTPException(404, "Movie not found")
            return JSONResponse(movie.to_dict())

        @router.put("/movies/{movie_id}")
        async def update_movie(movie_id: str, request: Request):
            if not self.db.get_movie(movie_id):
                raise HTTPException(404, "Movie not found")
            body = await request.json()
            allowed = {"title", "time_per_frame", "time_per_frame_unit", "skip_frames", "is_random"}
            updates = {k: v for k, v in body.items() if k in allowed}
            updated = self.db.update_movie(movie_id, updates)
            return JSONResponse({"success": True, "movie": updated.to_dict()})

        @router.delete("/movies/{movie_id}")
        async def delete_movie(movie_id: str):
            movie = self.db.get_movie(movie_id)
            if not movie:
                raise HTTPException(404, "Movie not found")
            self.db.delete_movie(movie_id)
            return JSONResponse({"success": True, "deleted_id": movie_id})

        @router.post("/movies/{movie_id}/activate")
        async def activate_movie(movie_id: str):
            movie = self.db.activate_movie(movie_id)
            if not movie:
                raise HTTPException(404, "Movie not found")
            return JSONResponse({"success": True, "movie": movie.to_dict()})

        @router.post("/movies/{movie_id}/advance")
        async def advance_movie(movie_id: str, request: Request):
            movie = self.db.get_movie(movie_id)
            if not movie:
                raise HTTPException(404, "Movie not found")
            body = {}
            try:
                body = await request.json()
            except Exception:
                pass
            resolution = body.get("resolution")
            result = await self.request_image({
                "movie_id": movie_id,
                "advance": True,
                "resolution": resolution,
            })
            if not result.get("success"):
                raise HTTPException(500, result.get("error", "Advance failed"))
            # Return frame as image
            frame_bytes = result.pop("bytes", None)
            result.pop("image", None)  # don't include base64 blob in JSON
            result["frame_bytes_size"] = len(frame_bytes) if frame_bytes else 0
            return JSONResponse(result)

        @router.post("/movies/{movie_id}/seek")
        async def seek_movie(movie_id: str, request: Request):
            movie = self.db.get_movie(movie_id)
            if not movie:
                raise HTTPException(404, "Movie not found")
            body = await request.json()
            frame = int(body.get("frame", 0))
            if movie.total_frames > 0:
                frame = max(0, min(frame, movie.total_frames - 1))
            self.db.update_movie(movie_id, {"current_frame": frame})
            return JSONResponse({"success": True, "movie_id": movie_id, "current_frame": frame})

        # --- Upload ------------------------------------------------------

        @router.post("/upload")
        async def upload_video(file: UploadFile = File(...)):
            if not file.filename:
                raise HTTPException(400, "No filename provided")

            ext = Path(file.filename).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                raise HTTPException(400, f"Unsupported format: {ext}. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}")

            # Save file
            safe_name = f"{uuid.uuid4().hex}{ext}"
            dest = self.uploads_dir / safe_name
            dest.parent.mkdir(parents=True, exist_ok=True)

            content = await file.read()
            if not content:
                raise HTTPException(400, "Empty file")
            dest.write_bytes(content)

            # Introspect video
            info = VideoService.get_video_info(dest)
            if info["total_frames"] == 0:
                dest.unlink(missing_ok=True)
                raise HTTPException(422, "Could not read video metadata – ensure OpenCV is installed and file is valid")

            movie = Movie(
                id=str(uuid.uuid4()),
                title=Path(file.filename).stem,
                video_path=str(dest),
                added_at=datetime.now(timezone.utc).isoformat(),
                **{k: info[k] for k in ("total_frames", "fps", "width", "height", "duration_seconds")},
            )
            self.db.add_movie(movie)

            return JSONResponse({"success": True, "movie": movie.to_dict()}, status_code=201)

        # --- Current frame image -----------------------------------------

        @router.get("/frame/current")
        async def get_current_frame(movie_id: Optional[str] = None):
            movie = self.db.get_movie(movie_id) if movie_id else self.db.get_active_movie()
            if not movie:
                raise HTTPException(404, "No active movie" if not movie_id else "Movie not found")

            frame_bytes = self._render_frame(movie, movie.current_frame)
            if frame_bytes is None:
                # Serve placeholder
                placeholder = self.channel_dir / "placeholder.jpg"
                if placeholder.exists():
                    return FileResponse(str(placeholder), media_type="image/jpeg")
                raise HTTPException(500, "Frame extraction failed")

            from fastapi.responses import Response
            return Response(content=frame_bytes, media_type="image/jpeg")

        @router.post("/request_image")
        async def request_image_route(request: Request):
            body = {}
            try:
                body = await request.json()
            except Exception:
                pass
            result = await self.request_image(body)
            if not result.get("success"):
                raise HTTPException(500, result.get("error", "request_image failed"))
            frame_bytes = result.pop("bytes", None)
            result.pop("image", None)
            result["frame_bytes_size"] = len(frame_bytes) if frame_bytes else 0
            return JSONResponse(result)

        # --- External video directory scan -------------------------------

        @router.post("/scan")
        async def scan_video_directory(request: Request):
            body = {}
            try:
                body = await request.json()
            except Exception:
                pass
            settings = self.db.get_settings()
            scan_path = Path(body.get("path") or settings.video_root_path or "")
            if not scan_path or not scan_path.is_dir():
                raise HTTPException(400, f"Directory not found: {scan_path}")

            existing_paths = {m.video_path for m in self.db.list_movies()}
            added = []
            for f in scan_path.iterdir():
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                    if str(f) in existing_paths:
                        continue
                    info = VideoService.get_video_info(f)
                    if info["total_frames"] == 0:
                        continue
                    movie = Movie(
                        id=str(uuid.uuid4()),
                        title=f.stem,
                        video_path=str(f),
                        added_at=datetime.now(timezone.utc).isoformat(),
                        **{k: info[k] for k in ("total_frames", "fps", "width", "height", "duration_seconds")},
                    )
                    self.db.add_movie(movie)
                    added.append(movie.to_dict())

            return JSONResponse({"success": True, "added": len(added), "movies": added})

        logger.info("[SlowMovie] Router built with %d movies", len(self.db.list_movies()))
        return router


# Required export for Mimir plugin discovery
ChannelClass = SlowMovieChannel
