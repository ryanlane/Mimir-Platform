"""
Plugin Manager Service
Handles installation, uninstallation, enable/disable, and dev-channel linking
of channel plugins at runtime.
"""
import asyncio
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Name of the file that tracks which plugins are disabled
_DISABLED_FILE = "disabled_plugins.json"
# Name of the file that tracks dev-linked channels
_DEV_CHANNELS_FILE = "dev_channels.json"


class PluginManagerService:
    """Manage plugin installation, removal, and enable/disable state."""

    def __init__(self, channels_dir: str | None = None):
        self.channels_dir = Path(channels_dir or settings.channels_directory)

    # ------------------------------------------------------------------
    # Disabled-plugin persistence
    # ------------------------------------------------------------------

    def _disabled_file_path(self) -> Path:
        return self.channels_dir / _DISABLED_FILE

    def get_disabled_plugins(self) -> list[str]:
        """Return the list of currently disabled plugin IDs."""
        path = self._disabled_file_path()
        if not path.exists():
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read disabled plugins file: %s", exc)
        return []

    def _save_disabled_plugins(self, ids: list[str]) -> None:
        path = self._disabled_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(set(ids)), f, indent=2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_plugin_dir(self, path: Path) -> dict[str, Any]:
        """Validate a plugin directory. Returns parsed manifest dict or raises ValueError."""
        channel_file = path / "channel.py"
        if not channel_file.exists():
            raise ValueError(f"Plugin directory missing channel.py: {path.name}")

        config_file = path / "plugin.json"
        if not config_file.exists():
            config_file = path / "config.json"
        if not config_file.exists():
            raise ValueError(f"Plugin directory missing plugin.json (or config.json): {path.name}")

        try:
            with open(config_file, encoding="utf-8") as f:
                manifest = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {config_file.name}: {exc}") from exc

        required = ["id", "name", "description"]
        missing = [k for k in required if k not in manifest]
        if missing:
            raise ValueError(f"Manifest missing required fields: {', '.join(missing)}")

        return manifest

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    async def install_from_zip(self, file: UploadFile, app: FastAPI) -> dict[str, Any]:
        """Install a plugin from an uploaded ZIP file.

        Returns a dict with install results including the plugin ID on success.
        """
        from app.services.plugin_discovery import plugin_discovery_service

        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise ValueError("Uploaded file must be a .zip archive")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            zip_path = tmp_path / "upload.zip"

            # Write uploaded file to temp
            contents = await file.read()
            zip_path.write_bytes(contents)

            # Extract
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # Security: reject paths that escape the extraction dir
                    for member in zf.namelist():
                        resolved = (tmp_path / "extracted" / member).resolve()
                        if not str(resolved).startswith(str((tmp_path / "extracted").resolve())):
                            raise ValueError(f"Zip contains unsafe path: {member}")
                    zf.extractall(tmp_path / "extracted")
            except zipfile.BadZipFile as exc:
                raise ValueError(f"Invalid ZIP file: {exc}") from exc

            # Find the plugin root (may be nested one level)
            extracted = tmp_path / "extracted"
            plugin_root = self._find_plugin_root(extracted)
            if plugin_root is None:
                raise ValueError(
                    "Could not find a valid plugin directory in the archive "
                    "(expected channel.py + plugin.json/config.json)"
                )

            return await self._finalize_install(plugin_root, app, plugin_discovery_service)

    async def install_from_git(self, git_url: str, app: FastAPI) -> dict[str, Any]:
        """Install a plugin by cloning a Git repository.

        Returns a dict with install results including the plugin ID on success.
        """
        from app.services.plugin_discovery import plugin_discovery_service

        with tempfile.TemporaryDirectory() as tmp_dir:
            clone_dir = Path(tmp_dir) / "repo"
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git", "clone", "--depth", "1", git_url, str(clone_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                if proc.returncode != 0:
                    raise ValueError(
                        f"git clone failed (exit {proc.returncode}): {stderr.decode(errors='replace')[:500]}"
                    )
            except asyncio.TimeoutError:
                raise ValueError("git clone timed out after 120 seconds") from None

            plugin_root = self._find_plugin_root(clone_dir)
            if plugin_root is None:
                raise ValueError(
                    "Cloned repository does not contain a valid plugin directory "
                    "(expected channel.py + plugin.json/config.json)"
                )

            return await self._finalize_install(plugin_root, app, plugin_discovery_service)

    def _find_plugin_root(self, search_dir: Path) -> Path | None:
        """Locate the plugin root directory inside an extracted archive or cloned repo.

        The plugin root is the directory containing both ``channel.py`` and
        ``plugin.json`` (or ``config.json``).  We search up to 3 levels deep.
        """
        for depth_limit in range(4):
            for candidate in self._walk_max_depth(search_dir, depth_limit):
                if not candidate.is_dir():
                    continue
                has_channel = (candidate / "channel.py").exists()
                has_manifest = (candidate / "plugin.json").exists() or (candidate / "config.json").exists()
                if has_channel and has_manifest:
                    return candidate
        return None

    @staticmethod
    def _walk_max_depth(root: Path, max_depth: int):
        """Yield directories under *root* up to *max_depth* levels."""
        if max_depth == 0:
            yield root
            return
        if not root.is_dir():
            return
        yield root
        for child in root.iterdir():
            if child.is_dir():
                yield from PluginManagerService._walk_max_depth(child, max_depth - 1)

    async def _finalize_install(self, plugin_root: Path, app: FastAPI, discovery) -> dict[str, Any]:
        """Validate, move to channels dir, install deps, and hot-load the plugin."""
        manifest = self._validate_plugin_dir(plugin_root)
        plugin_id = manifest["id"]

        # Conflict check
        if discovery.get_plugin(plugin_id):
            raise ValueError(f"Plugin '{plugin_id}' is already installed")

        # Determine destination name
        dest_name = plugin_root.name
        # If the folder name is generic (e.g. "extracted"), use the plugin id
        if dest_name.lower() in ("extracted", "repo", "src", "plugin"):
            dest_name = plugin_id.replace(".", "_")
        dest_path = self.channels_dir / dest_name

        if dest_path.exists():
            raise ValueError(f"Destination directory already exists: {dest_name}")

        # Move to channels directory
        shutil.copytree(plugin_root, dest_path)
        logger.info("Installed plugin files to %s", dest_path)

        # Best-effort dependency installation
        req_file = dest_path / "requirements.txt"
        if req_file.exists():
            try:
                proc = subprocess.run(
                    ["pip", "install", "-r", str(req_file)],
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode != 0:
                    logger.warning(
                        "pip install for %s exited %d: %s",
                        plugin_id, proc.returncode, proc.stderr[:500],
                    )
            except Exception as exc:
                logger.warning("Failed installing dependencies for %s: %s", plugin_id, exc)

        # Hot-reload: load the plugin into the running app
        try:
            plugin = await discovery.load_single_plugin(dest_path, app)
            healthy = plugin.healthy if plugin else False
        except Exception as exc:
            logger.error("Hot-reload failed for %s: %s", plugin_id, exc)
            healthy = False

        # Remove from disabled list if it was there
        disabled = self.get_disabled_plugins()
        if plugin_id in disabled:
            disabled.remove(plugin_id)
            self._save_disabled_plugins(disabled)

        return {
            "plugin_id": plugin_id,
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "installed_path": str(dest_path),
            "healthy": healthy,
        }

    # ------------------------------------------------------------------
    # Uninstall
    # ------------------------------------------------------------------

    async def uninstall(self, plugin_id: str, app: FastAPI) -> dict[str, Any]:
        """Uninstall a plugin: unload, remove from disk, clean up state."""
        from app.services.plugin_discovery import plugin_discovery_service

        plugin = plugin_discovery_service.get_plugin(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_id}' is not installed")

        plugin_path = plugin.plugin_path

        # Unload from running server
        await plugin_discovery_service.unload_plugin(plugin_id, app)

        # Remove from disabled list if present
        disabled = self.get_disabled_plugins()
        if plugin_id in disabled:
            disabled.remove(plugin_id)
            self._save_disabled_plugins(disabled)

        # Delete from disk
        if plugin_path.exists():
            shutil.rmtree(plugin_path, ignore_errors=True)
            logger.info("Removed plugin directory: %s", plugin_path)

        return {"plugin_id": plugin_id, "uninstalled": True}

    # ------------------------------------------------------------------
    # Enable / Disable
    # ------------------------------------------------------------------

    async def disable(self, plugin_id: str, app: FastAPI) -> dict[str, Any]:
        """Disable a plugin: unload from server, mark as disabled, keep on disk."""
        from app.services.plugin_discovery import plugin_discovery_service

        plugin = plugin_discovery_service.get_plugin(plugin_id)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_id}' is not installed")

        # Unload from running server
        await plugin_discovery_service.unload_plugin(plugin_id, app)

        # Persist disabled state
        disabled = self.get_disabled_plugins()
        if plugin_id not in disabled:
            disabled.append(plugin_id)
            self._save_disabled_plugins(disabled)

        return {"plugin_id": plugin_id, "enabled": False}

    async def enable(self, plugin_id: str, app: FastAPI) -> dict[str, Any]:
        """Enable a previously disabled plugin: reload it and remove from disabled list."""
        from app.services.plugin_discovery import plugin_discovery_service

        # Check it's actually disabled
        disabled = self.get_disabled_plugins()
        if plugin_id not in disabled:
            raise ValueError(f"Plugin '{plugin_id}' is not disabled")

        # Find the plugin directory on disk
        plugin_dir = self._find_plugin_dir_by_id(plugin_id)
        if plugin_dir is None:
            raise ValueError(f"Plugin directory for '{plugin_id}' not found on disk")

        # Re-load the plugin
        plugin = await plugin_discovery_service.load_single_plugin(plugin_dir, app)
        healthy = plugin.healthy if plugin else False

        # Remove from disabled list
        disabled.remove(plugin_id)
        self._save_disabled_plugins(disabled)

        return {"plugin_id": plugin_id, "enabled": True, "healthy": healthy}

    def _find_plugin_dir_by_id(self, plugin_id: str) -> Path | None:
        """Scan the channels directory for a plugin matching the given ID."""
        for candidate in self.channels_dir.iterdir():
            if not candidate.is_dir():
                continue
            for config_name in ("plugin.json", "config.json"):
                config_file = candidate / config_name
                if config_file.exists():
                    try:
                        with open(config_file, encoding="utf-8") as f:
                            data = json.load(f)
                        if data.get("id") == plugin_id:
                            return candidate
                    except (json.JSONDecodeError, OSError):
                        continue
        return None

    # ------------------------------------------------------------------
    # Dev Channel Management
    # ------------------------------------------------------------------

    def _dev_channels_file_path(self) -> Path:
        return self.channels_dir / _DEV_CHANNELS_FILE

    def get_dev_channels(self) -> list[dict[str, Any]]:
        """Return the list of dev-linked channel entries."""
        path = self._dev_channels_file_path()
        if not path.exists():
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read dev channels file: %s", exc)
        return []

    def _save_dev_channels(self, entries: list[dict[str, Any]]) -> None:
        path = self._dev_channels_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

    def get_dev_channel_ids(self) -> set:
        """Return a set of plugin IDs that are dev-linked."""
        return {e["plugin_id"] for e in self.get_dev_channels() if "plugin_id" in e}

    async def link_dev_channel(self, path_str: str, app: FastAPI) -> dict[str, Any]:
        """Link a local directory as a dev channel.

        The directory is loaded in-place (no copy) and a file watcher is started.
        """
        from app.services.dev_watcher import dev_watcher_service
        from app.services.plugin_discovery import plugin_discovery_service

        dev_path = Path(path_str).resolve()

        if not dev_path.exists():
            raise ValueError(f"Path does not exist: {dev_path}")
        if not dev_path.is_dir():
            raise ValueError(f"Path is not a directory: {dev_path}")

        # Validate the directory has the required plugin files
        manifest = self._validate_plugin_dir(dev_path)
        plugin_id = manifest["id"]

        # Conflict check
        if plugin_discovery_service.get_plugin(plugin_id):
            raise ValueError(f"Plugin '{plugin_id}' is already loaded")

        # Check not already in dev list
        existing = self.get_dev_channels()
        if any(e.get("plugin_id") == plugin_id for e in existing):
            raise ValueError(f"Dev channel '{plugin_id}' is already linked")

        # Load the plugin
        plugin = await plugin_discovery_service.load_single_plugin(dev_path, app)
        healthy = plugin.healthy if plugin else False

        # Persist dev channel entry
        existing.append({
            "path": str(dev_path),
            "plugin_id": plugin_id,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_dev_channels(existing)

        # Start file watcher
        dev_watcher_service.watch(plugin_id, dev_path)

        logger.info("Linked dev channel: %s at %s", plugin_id, dev_path)
        return {
            "plugin_id": plugin_id,
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "path": str(dev_path),
            "healthy": healthy,
        }

    async def unlink_dev_channel(self, plugin_id: str, app: FastAPI) -> dict[str, Any]:
        """Unlink a dev channel: unload from server, stop watcher, remove from registry.

        Does NOT delete any files on disk.
        """
        from app.services.dev_watcher import dev_watcher_service
        from app.services.plugin_discovery import plugin_discovery_service

        entries = self.get_dev_channels()
        entry = next((e for e in entries if e.get("plugin_id") == plugin_id), None)
        if entry is None:
            raise ValueError(f"'{plugin_id}' is not a dev channel")

        # Stop watcher
        dev_watcher_service.unwatch(plugin_id)

        # Unload from running server
        await plugin_discovery_service.unload_plugin(plugin_id, app)

        # Remove from dev channels list
        entries = [e for e in entries if e.get("plugin_id") != plugin_id]
        self._save_dev_channels(entries)

        logger.info("Unlinked dev channel: %s", plugin_id)
        return {"plugin_id": plugin_id, "unlinked": True}

    async def reload_dev_channel(self, plugin_id: str, app: FastAPI) -> dict[str, Any]:
        """Manually reload a dev channel (unload + re-load from same path)."""
        from app.services.plugin_discovery import plugin_discovery_service

        entries = self.get_dev_channels()
        entry = next((e for e in entries if e.get("plugin_id") == plugin_id), None)
        if entry is None:
            raise ValueError(f"'{plugin_id}' is not a dev channel")

        dev_path = Path(entry["path"])
        if not dev_path.exists():
            raise ValueError(f"Dev channel path no longer exists: {dev_path}")

        # Unload current instance
        await plugin_discovery_service.unload_plugin(plugin_id, app)

        # Re-load
        plugin = await plugin_discovery_service.load_single_plugin(dev_path, app)
        healthy = plugin.healthy if plugin else False

        logger.info("Reloaded dev channel: %s (healthy=%s)", plugin_id, healthy)
        return {"plugin_id": plugin_id, "reloaded": True, "healthy": healthy}

    async def load_dev_channels_on_startup(self, app: FastAPI) -> None:
        """Load all dev channels from dev_channels.json on server startup.

        Called after normal plugin discovery. Also starts file watchers.
        """
        from app.services.dev_watcher import dev_watcher_service
        from app.services.plugin_discovery import plugin_discovery_service

        entries = self.get_dev_channels()
        if not entries:
            return

        logger.info("[dev] Loading %d dev channel(s) from dev_channels.json", len(entries))
        valid_entries = []

        for entry in entries:
            dev_path = Path(entry.get("path", ""))
            plugin_id = entry.get("plugin_id", "")

            if not dev_path.exists():
                logger.warning("[dev] Dev channel path missing, skipping: %s (%s)", plugin_id, dev_path)
                continue

            # Skip if already loaded (e.g., if the dev dir is inside channels_directory)
            if plugin_discovery_service.get_plugin(plugin_id):
                logger.debug("[dev] %s already loaded, starting watcher only", plugin_id)
                dev_watcher_service.watch(plugin_id, dev_path)
                valid_entries.append(entry)
                continue

            try:
                plugin = await plugin_discovery_service.load_single_plugin(dev_path, app)
                if plugin:
                    dev_watcher_service.watch(plugin_id, dev_path)
                    logger.info("[dev] Loaded dev channel: %s from %s", plugin_id, dev_path)
                    valid_entries.append(entry)
                else:
                    logger.warning("[dev] Failed to load dev channel: %s", plugin_id)
            except Exception as exc:
                logger.error("[dev] Error loading dev channel %s: %s", plugin_id, exc)

        # Save back only the entries that are still valid
        if len(valid_entries) != len(entries):
            self._save_dev_channels(valid_entries)


# Global service instance
plugin_manager_service = PluginManagerService()
