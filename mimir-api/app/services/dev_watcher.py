"""
Dev Watcher Service
Monitors dev channel directories for file changes and triggers automatic reloads.
Uses the watchdog library for cross-platform file system monitoring.
"""
import asyncio
import os
import threading
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Extensions we care about for reload triggers
_WATCHED_EXTENSIONS = {".py", ".json", ".html", ".js", ".css", ".mjs"}

# Directories to ignore
_IGNORED_DIRS = {"__pycache__", ".git", "node_modules", "data", ".mypy_cache", ".pytest_cache", "venv", ".venv"}

# Debounce interval in seconds
_DEBOUNCE_SECONDS = 1.5


class _ChangeHandler:
    """Watchdog event handler that schedules debounced reloads."""

    def __init__(self, plugin_id: str, plugin_path: Path, watcher: "DevWatcherService"):
        self.plugin_id = plugin_id
        self.plugin_path = plugin_path
        self._watcher = watcher

    def dispatch(self, event):
        """Called by watchdog on any file system event."""
        # Only care about file modifications, creations, and moves
        if event.is_directory:
            return

        src_path = Path(event.src_path)

        # Check extension filter
        if src_path.suffix.lower() not in _WATCHED_EXTENSIONS:
            return

        # Check ignored directories
        for part in src_path.parts:
            if part in _IGNORED_DIRS:
                return

        logger.debug(
            "[dev-watcher] File change detected for %s: %s (%s)",
            self.plugin_id,
            src_path.name,
            event.event_type,
        )
        self._watcher._schedule_reload(self.plugin_id)


class DevWatcherService:
    """Watches dev channel directories for file changes and auto-reloads plugins."""

    def __init__(self):
        self._observer = None  # Lazy-initialized watchdog Observer
        self._watches: dict[str, Any] = {}  # plugin_id -> ObservedWatch
        self._handlers: dict[str, _ChangeHandler] = {}
        self._pending_timers: dict[str, threading.Timer] = {}
        self._app = None  # FastAPI app reference for reload operations
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False

    def start(self, app: Any) -> None:
        """Start the file watcher observer thread."""
        try:
            from watchdog.observers import Observer
            from watchdog.observers.polling import PollingObserver
        except ImportError:
            logger.warning(
                "[dev-watcher] watchdog is not installed. "
                "Dev channel auto-reload will not work. "
                "Install with: pip install watchdog"
            )
            return

        def _in_docker() -> bool:
            # Common marker file in Docker containers
            if os.path.exists("/.dockerenv"):
                return True
            # Heuristic: cgroup info often includes 'docker' or 'containerd'
            try:
                with open("/proc/1/cgroup", encoding="utf-8") as f:
                    s = f.read()
                return "docker" in s or "containerd" in s
            except Exception:
                return False

        mode = os.getenv("DEV_WATCHER_MODE", "auto").strip().lower()
        polling_interval = float(os.getenv("DEV_WATCHER_POLLING_INTERVAL", "1.0"))
        use_polling = (mode == "polling") or (mode == "auto" and _in_docker())

        self._app = app
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self._observer = PollingObserver(timeout=polling_interval) if use_polling else Observer()
        self._observer.daemon = True
        self._observer.start()
        self._started = True
        logger.info(
            "[dev-watcher] File watcher started (mode=%s%s)",
            "polling" if use_polling else "native",
            f", interval={polling_interval}s" if use_polling else "",
        )

    def stop(self) -> None:
        """Stop the file watcher observer thread and cancel pending timers."""
        # Cancel all pending reload timers
        for timer in self._pending_timers.values():
            timer.cancel()
        self._pending_timers.clear()

        if self._observer and self._started:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._started = False
            logger.info("[dev-watcher] File watcher stopped")

    def watch(self, plugin_id: str, path: Path) -> None:
        """Start watching a dev channel directory for changes."""
        if not self._started or self._observer is None:
            logger.warning("[dev-watcher] Observer not started, cannot watch %s", plugin_id)
            return

        # Don't double-watch
        if plugin_id in self._watches:
            logger.debug("[dev-watcher] Already watching %s", plugin_id)
            return

        handler = _ChangeHandler(plugin_id, path, self)
        self._handlers[plugin_id] = handler

        try:
            from watchdog.events import FileSystemEventHandler

            # Create a proper watchdog handler wrapper
            class _WatchdogAdapter(FileSystemEventHandler):
                def __init__(self, change_handler):
                    self._ch = change_handler

                def on_any_event(self, event):
                    self._ch.dispatch(event)

            adapter = _WatchdogAdapter(handler)
            watch = self._observer.schedule(adapter, str(path), recursive=True)
            self._watches[plugin_id] = watch
            logger.info("[dev-watcher] Watching %s at %s", plugin_id, path)
        except Exception as exc:
            logger.error("[dev-watcher] Failed to watch %s: %s", plugin_id, exc)

    def unwatch(self, plugin_id: str) -> None:
        """Stop watching a dev channel directory."""
        # Cancel any pending reload
        timer = self._pending_timers.pop(plugin_id, None)
        if timer:
            timer.cancel()

        watch = self._watches.pop(plugin_id, None)
        self._handlers.pop(plugin_id, None)

        if watch and self._observer:
            try:
                self._observer.unschedule(watch)
            except Exception:
                pass  # May already be unscheduled
            logger.info("[dev-watcher] Stopped watching %s", plugin_id)

    def _schedule_reload(self, plugin_id: str) -> None:
        """Schedule a debounced reload for the given plugin.

        If a reload is already pending, it is cancelled and a new timer starts.
        This ensures we don't reload multiple times for a burst of file changes
        (e.g., saving multiple files at once, or editor atomic writes).
        """
        # Cancel existing timer
        existing = self._pending_timers.pop(plugin_id, None)
        if existing:
            existing.cancel()

        def _fire():
            self._pending_timers.pop(plugin_id, None)
            logger.info("[dev-watcher] Auto-reloading dev channel: %s", plugin_id)
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self._do_reload(plugin_id), self._loop)
            else:
                logger.warning("[dev-watcher] No running event loop for reload of %s", plugin_id)

        timer = threading.Timer(_DEBOUNCE_SECONDS, _fire)
        timer.daemon = True
        self._pending_timers[plugin_id] = timer
        timer.start()

    async def _do_reload(self, plugin_id: str) -> None:
        """Perform the actual plugin unload + reload cycle."""
        from app.services.plugin_discovery import plugin_discovery_service

        plugin = plugin_discovery_service.get_plugin(plugin_id)
        if not plugin:
            logger.warning("[dev-watcher] Plugin %s no longer loaded, skipping reload", plugin_id)
            return

        plugin_path = plugin.plugin_path

        try:
            await plugin_discovery_service.unload_plugin(plugin_id, self._app)
            reloaded = await plugin_discovery_service.load_single_plugin(plugin_path, self._app)
            if reloaded and reloaded.healthy:
                logger.info("[dev-watcher] Successfully reloaded %s", plugin_id)
            else:
                logger.warning("[dev-watcher] Reloaded %s but plugin is unhealthy", plugin_id)
        except Exception as exc:
            logger.error("[dev-watcher] Failed to reload %s: %s", plugin_id, exc)


# Global service instance
dev_watcher_service = DevWatcherService()
