"""Data models for the Slow Movie channel."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Movie:
    id: str
    title: str
    video_path: str
    total_frames: int = 0
    current_frame: int = 0
    # Per-movie override (None = inherit global skip_frames)
    skip_frames: Optional[int] = None
    is_random: bool = False
    # Playback behaviour
    loop: bool = True
    start_frame: int = 0
    end_frame: Optional[int] = None
    # Output appearance
    fit_mode: str = "letterbox"  # "letterbox" | "crop" | "stretch"
    grayscale: bool = False
    dither_mode: str = "none"   # "none" | "floyd_steinberg" | "atkinson"
    added_at: str = ""
    last_played_at: Optional[str] = None
    # Computed display info
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        start = self.start_frame or 0
        end = self.end_frame if self.end_frame is not None else max(0, self.total_frames - 1)
        clip_length = max(1, end - start + 1)
        relative_frame = max(0, self.current_frame - start)
        d["progress_pct"] = round(relative_frame / clip_length * 100, 1)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Movie":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class GlobalSettings:
    skip_frames: int = 1
    video_root_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalSettings":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})



class MovieDatabase:
    """JSON-backed movie library and settings store."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._movies_path = data_dir / "movies.json"
        self._settings_path = data_dir / "settings.json"
        self._movies: Dict[str, Movie] = {}
        self._settings: GlobalSettings = GlobalSettings()
        self._load()

    # -------------------------------------------------------------------------
    # Persistence

    def _load(self) -> None:
        if self._movies_path.exists():
            try:
                raw = json.loads(self._movies_path.read_text())
                self._movies = {mid: Movie.from_dict(m) for mid, m in raw.items()}
            except Exception:
                self._movies = {}
        if self._settings_path.exists():
            try:
                raw = json.loads(self._settings_path.read_text())
                self._settings = GlobalSettings.from_dict(raw)
            except Exception:
                self._settings = GlobalSettings()

    def _save_movies(self) -> None:
        self._movies_path.write_text(
            json.dumps({mid: m.to_dict() for mid, m in self._movies.items()}, indent=2)
        )

    def _save_settings(self) -> None:
        self._settings_path.write_text(json.dumps(self._settings.to_dict(), indent=2))

    # -------------------------------------------------------------------------
    # Movies

    def list_movies(self) -> List[Movie]:
        return list(self._movies.values())

    def get_movie(self, movie_id: str) -> Optional[Movie]:
        return self._movies.get(movie_id)

    def add_movie(self, movie: Movie) -> Movie:
        self._movies[movie.id] = movie
        self._save_movies()
        return movie

    def update_movie(self, movie_id: str, updates: Dict[str, Any]) -> Optional[Movie]:
        movie = self._movies.get(movie_id)
        if not movie:
            return None
        for k, v in updates.items():
            if hasattr(movie, k):
                setattr(movie, k, v)
        self._save_movies()
        return movie

    def delete_movie(self, movie_id: str) -> bool:
        if movie_id not in self._movies:
            return False
        del self._movies[movie_id]
        self._save_movies()
        return True

    # -------------------------------------------------------------------------
    # Settings

    def get_settings(self) -> GlobalSettings:
        return self._settings

    def update_settings(self, updates: Dict[str, Any]) -> GlobalSettings:
        for k, v in updates.items():
            if hasattr(self._settings, k):
                setattr(self._settings, k, v)
        self._save_settings()
        return self._settings
