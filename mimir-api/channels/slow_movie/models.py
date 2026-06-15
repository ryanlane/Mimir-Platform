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
    # Per-movie overrides (None = inherit global setting)
    time_per_frame: Optional[int] = None
    time_per_frame_unit: Optional[str] = None
    skip_frames: Optional[int] = None
    is_active: bool = False
    is_random: bool = False
    added_at: str = ""
    last_played_at: Optional[str] = None
    # Computed display info
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Compute progress percentage
        d["progress_pct"] = round(self.current_frame / self.total_frames * 100, 1) if self.total_frames > 0 else 0.0
        # Compute estimated completion (in days) based on effective settings
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Movie":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class GlobalSettings:
    time_per_frame: int = 30
    time_per_frame_unit: str = "minutes"
    skip_frames: int = 1
    use_quiet_hours: bool = False
    quiet_start: int = 22
    quiet_end: int = 7
    video_root_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalSettings":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def time_per_frame_seconds(self) -> int:
        multipliers = {"seconds": 1, "minutes": 60, "hours": 3600}
        return self.time_per_frame * multipliers.get(self.time_per_frame_unit, 60)


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

    def get_active_movie(self) -> Optional[Movie]:
        for m in self._movies.values():
            if m.is_active:
                return m
        return None

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

    def activate_movie(self, movie_id: str) -> Optional[Movie]:
        if movie_id not in self._movies:
            return None
        # Deactivate all others
        for m in self._movies.values():
            m.is_active = False
        self._movies[movie_id].is_active = True
        self._save_movies()
        return self._movies[movie_id]

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
