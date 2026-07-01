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
Plugin Discovery Service for Embedded Channel Architecture
Handles discovery and loading of channel plugins into the main API process
"""
import asyncio
import importlib.util
import json
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.logging import get_logger
from app.services.channel_event_consumer import channel_event_consumer
from app.services.channel_events import ChannelUpdateEvent, channel_event_dispatcher

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Protocol validation helpers
# ---------------------------------------------------------------------------
_REQUIRED_METHODS = ("get_router", "get_manifest", "request_image")
_OPTIONAL_METHODS = ("get_status", "on_startup", "on_shutdown", "register_listener",
                     "unregister_listener", "stop")


def _validate_channel_protocol(instance: Any, plugin_id: str) -> list[str]:
    """Check that *instance* satisfies the required channel protocol.

    Returns a list of missing method names (empty == valid).
    """
    missing = [m for m in _REQUIRED_METHODS if not callable(getattr(instance, m, None))]
    if missing:
        logger.warning(
            "[plugins] %s: missing required methods: %s",
            plugin_id,
            ", ".join(missing),
        )
    return missing


class _IsolatedPluginRoute(APIRoute):
    """APIRoute subclass that catches unhandled exceptions in plugin handlers.

    Prevents a single buggy plugin route from crashing the entire API server
    by returning a 500 JSON response instead of letting the exception propagate
    to the ASGI server.
    """

    def __init__(self, *args: Any, plugin_id: str = "unknown", **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._plugin_id = plugin_id

    def get_route_handler(self):
        original = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await original(request)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "[plugins] Unhandled exception in plugin %s route %s %s: %s",
                    self._plugin_id,
                    request.method,
                    request.url.path,
                    exc,
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": f"Plugin error in {self._plugin_id}",
                        "error": str(exc),
                    },
                )

        return wrapped


@dataclass
class ChannelPlugin:
    """Represents a discovered channel plugin"""
    id: str
    name: str
    description: str
    icon: str | None
    config_path: Path
    plugin_path: Path
    instance: Any | None = None
    last_health_check: float | None = None
    healthy: bool = True  # Embedded plugins are healthy if loaded


class PluginDiscoveryService:
    """Service for discovering and managing embedded channel plugins"""

    def __init__(self, channels_dir: str | None = None):
        self.channels_dir = Path(channels_dir or settings.channels_directory)
        self.plugins: dict[str, ChannelPlugin] = {}

    def _get_disabled_plugin_ids(self) -> set:
        """Read the disabled_plugins.json file and return a set of disabled IDs."""
        disabled_file = self.channels_dir / "disabled_plugins.json"
        if not disabled_file.exists():
            return set()
        try:
            with open(disabled_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {str(x) for x in data}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read disabled_plugins.json: %s", exc)
        return set()

    async def discover_plugins(self, app: FastAPI) -> list[ChannelPlugin]:
        """Discover and load channel plugins into the main API"""
        if not self.channels_dir.exists():
            self.channels_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created channels directory: {self.channels_dir}")
            return []

        disabled_ids = self._get_disabled_plugin_ids()
        if disabled_ids:
            logger.info("[plugins] Disabled plugins: %s", ", ".join(sorted(disabled_ids)))

        discovered_plugins = []
        logger.info(f"Scanning for channel plugins in: {self.channels_dir}")

        for plugin_path in self.channels_dir.iterdir():
            if not plugin_path.is_dir():
                continue
            # Skip hidden directories and common non-plugin directories
            if (plugin_path.name.startswith('.') or
                    plugin_path.name.lower() in {'assets', 'data', 'static', 'uploads', 'cache', 'temp', 'logs'}):
                continue
            config_file = plugin_path / "plugin.json"
            if not config_file.exists():
                logger.debug("[plugins] %s: missing plugin.json, checking config.json", plugin_path.name)
                config_file = plugin_path / "config.json"
                if not config_file.exists():
                    logger.debug("[plugins] %s: no config file present, skipping", plugin_path.name)
                    continue
            try:
                logger.debug("[plugins] Loading config for %s", plugin_path)
                plugin = await self._load_plugin_config(config_file, plugin_path)
                if not plugin:
                    logger.debug("[plugins] %s: config load returned None", plugin_path.name)
                    continue
                # Skip disabled plugins
                if plugin.id in disabled_ids:
                    logger.info("[plugins] Skipping disabled plugin: %s", plugin.id)
                    continue
                logger.debug("[plugins] %s: config loaded (id=%s) – loading instance", plugin_path.name, plugin.id)
                await self._load_plugin_instance(plugin, app)
                discovered_plugins.append(plugin)
                self.plugins[plugin.id] = plugin
                logger.info("Discovered plugin: %s at %s (healthy=%s)", plugin.id, plugin.plugin_path, plugin.healthy)
            except Exception as e:  # noqa: BLE001
                logger.error("Error loading plugin from %s: %s", plugin_path, e)
                if logger.isEnabledFor(10):
                    logger.debug("Traceback loading %s:\n%s", plugin_path, traceback.format_exc(limit=10))

        logger.info(f"Plugin discovery complete. Found {len(discovered_plugins)} plugins")
        return discovered_plugins

    async def _load_plugin_config(self, config_file: Path, plugin_path: Path) -> ChannelPlugin | None:
        """Load plugin configuration from plugin.json or config.json"""
        try:
            with open(config_file, encoding='utf-8') as f:
                config = json.load(f)
            if config_file.name == "plugin.json":
                required = ['id', 'name', 'description']
                missing = [k for k in required if k not in config]
                if missing:
                    logger.warning("Plugin %s missing required fields: %s", plugin_path.name, missing)
                    return None
                return ChannelPlugin(
                    id=config['id'],
                    name=config['name'],
                    description=config['description'],
                    icon=config.get('icon'),
                    config_path=config_file,
                    plugin_path=plugin_path
                )
            # legacy config.json path
            required = ['name', 'description']
            missing = [k for k in required if k not in config]
            if missing:
                logger.warning("Legacy plugin %s missing required fields: %s", plugin_path.name, missing)
                return None
            plugin_id = config.get('id', plugin_path.name)
            return ChannelPlugin(
                id=plugin_id,
                name=config['name'],
                description=config['description'],
                icon=config.get('icon'),
                config_path=config_file,
                plugin_path=plugin_path
            )
        except json.JSONDecodeError as e:
            logger.error("Error parsing %s for %s: %s", config_file.name, plugin_path.name, e)
            return None

    async def _load_plugin_instance(self, plugin: ChannelPlugin, app: FastAPI):
        """Load and initialize plugin instance"""
        try:
            # Look for channel.py file
            channel_file = plugin.plugin_path / "channel.py"
            if not channel_file.exists():
                logger.warning(f"No channel.py found for plugin {plugin.id}")
                plugin.healthy = False
                return
            logger.debug(f"[plugins] ({plugin.id}) Checking for channel.py at {channel_file}")

            # Use package-aware loading when __init__.py exists, otherwise
            # fall back to the legacy file-path based import.
            module = self._import_plugin_module(plugin)
            if module is None:
                plugin.healthy = False
                return
            logger.debug(f"[plugins] ({plugin.id}) Module loaded; searching for channel class")

            # Find and instantiate the channel class
            channel_class = self._find_channel_class(module, plugin.id)
            if not channel_class:
                logger.error(f"No suitable channel class found for {plugin.id}")
                plugin.healthy = False
                return

            logger.info(f"Found channel class for {plugin.id}: {channel_class.__name__} from {channel_class.__module__}")

            # Instantiate the channel
            try:
                logger.debug(f"[plugins] ({plugin.id}) Instantiating channel class {channel_class.__name__}")
                plugin.instance = channel_class(str(plugin.plugin_path))
            except Exception as inst_exc:
                plugin.healthy = False
                logger.error(f"Failed instantiating channel {plugin.id}: {inst_exc}")
                if logger.isEnabledFor(10):
                    logger.debug("Traceback: %s", traceback.format_exc(limit=12))
                return

            # Validate channel protocol
            missing = _validate_channel_protocol(plugin.instance, plugin.id)
            if missing:
                logger.warning(
                    "[plugins] %s loaded with missing methods (%s) – "
                    "plugin may not function correctly",
                    plugin.id,
                    ", ".join(missing),
                )

            # Mount plugin router if available
            if hasattr(plugin.instance, 'get_router'):
                try:
                    router = plugin.instance.get_router()
                except Exception as r_exc:
                    logger.error(f"Router construction failed for {plugin.id}: {r_exc}")
                    if logger.isEnabledFor(10):
                        logger.debug("Traceback: %s", traceback.format_exc(limit=12))
                    plugin.healthy = False
                    return
                if router:
                    # Wrap routes with exception isolation
                    router.route_class = type(
                        f"_Isolated_{plugin.id}",
                        (_IsolatedPluginRoute,),
                        {"_plugin_id": plugin.id},
                    )
                    mount_path = f"/api/channels/{plugin.id}"
                    app.include_router(router, prefix=mount_path, tags=[f"plugin-{plugin.id}"])
                    logger.info(f"Mounted plugin router: {mount_path}")
                else:
                    logger.warning(f"get_router returned None for {plugin.id}")

            # Mount static assets
            self._mount_static_assets(app, plugin)

            plugin.healthy = True
            logger.info(f"Successfully loaded plugin instance for {plugin.id}")

            # Call on_startup lifecycle hook if implemented
            if hasattr(plugin.instance, 'on_startup'):
                try:
                    plugin.instance.on_startup()
                    logger.info(f"Called on_startup for plugin {plugin.id}")
                except Exception as startup_exc:  # noqa: BLE001
                    logger.warning(f"on_startup failed for {plugin.id}: {startup_exc}")

            # Register push listener if plugin advertises push capability
            try:
                inst = plugin.instance
                if getattr(inst, "supports_push", False) and hasattr(inst, "register_listener"):
                    # Define listener callback bridging to central dispatcher
                    # Capture the main event loop to allow cross-thread scheduling from PushManager thread
                    try:
                        main_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        # Fallback for environments where get_running_loop isn't available here; best-effort
                        main_loop = None  # type: ignore[assignment]

                    def _on_channel_event(raw_evt: dict):  # raw dict from plugin (thread context allowed)
                        # Build event and publish it into the API's dispatcher from any thread.
                        try:
                            evt = ChannelUpdateEvent(
                                channel_id=raw_evt.get("channel_id", plugin.id),
                                event_type=raw_evt.get("event_type", "update"),
                                payload=raw_evt.get("payload", {}),
                                ts=raw_evt.get("ts") or time.time(),
                                version=raw_evt.get("version", 1),
                                hash=raw_evt.get("hash")
                            )
                        except Exception as build_exc:  # noqa: BLE001
                            logger.warning(f"Failed constructing ChannelUpdateEvent for {plugin.id}: {build_exc}")
                            return
                        # Schedule coroutine safely using the captured loop (thread-safe)
                        try:
                            if main_loop and main_loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    channel_event_dispatcher.publish(evt), main_loop
                                )
                            else:
                                # As a last resort, try current thread's loop if present
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    loop.create_task(channel_event_dispatcher.publish(evt))
                        except Exception:
                            # Avoid crashing plugin thread on scheduling errors
                            pass
                    inst.register_listener(_on_channel_event)
                    logger.info(f"Registered push listener for plugin {plugin.id}")
                    # Ensure global consumer service is started (subscription & stale loop)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(channel_event_consumer.ensure_subscription())
                    except RuntimeError:
                        pass
                    # Register consumer subscription (async) after loop available
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(channel_event_consumer.register_channel(plugin.id))
                    except RuntimeError:
                        pass
            except Exception as push_err:  # noqa: BLE001
                logger.warning(f"Failed to register push listener for {plugin.id}: {push_err}")

        except Exception as e:
            logger.error(f"Error loading plugin instance for {plugin.id}: {e}")
            plugin.healthy = False

    def _import_plugin_module(self, plugin: ChannelPlugin) -> Any | None:
        """Import the plugin's channel module.

        Strategy:
          1. If the plugin directory contains ``__init__.py``, import as a
             proper Python package so relative imports (``from . import X``)
             work naturally.
          2. Otherwise, fall back to the legacy ``spec_from_file_location``
             approach for backward compatibility.
        """
        plugin_dir = plugin.plugin_path
        channel_file = plugin_dir / "channel.py"
        pkg_name = f"mimir_plugin_{plugin.id.replace('.', '_')}"

        if (plugin_dir / "__init__.py").exists():
            # --- Package import path ---
            # Ensure the *parent* of the plugin dir is on sys.path so that
            # ``import mimir_plugin_com_foo_bar`` resolves to the directory.
            parent_dir = str(plugin_dir.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            # Register the package itself
            try:
                pkg_spec = importlib.util.spec_from_file_location(
                    pkg_name,
                    plugin_dir / "__init__.py",
                    submodule_search_locations=[str(plugin_dir)],
                )
                if pkg_spec is None or pkg_spec.loader is None:
                    logger.error(f"[plugins] ({plugin.id}) Could not create package spec")
                    return None
                pkg_mod = importlib.util.module_from_spec(pkg_spec)
                sys.modules[pkg_name] = pkg_mod
                pkg_spec.loader.exec_module(pkg_mod)  # type: ignore[union-attr]
            except Exception as e:  # noqa: BLE001
                logger.error(f"[plugins] ({plugin.id}) Package __init__ failed: {e}")
                if logger.isEnabledFor(10):
                    logger.debug("Traceback:\n%s", traceback.format_exc(limit=10))
                return None

            # Now import the channel sub-module
            channel_mod_name = f"{pkg_name}.channel"
            try:
                spec = importlib.util.spec_from_file_location(
                    channel_mod_name,
                    channel_file,
                    submodule_search_locations=None,
                )
                if spec is None or spec.loader is None:
                    logger.error(f"[plugins] ({plugin.id}) Could not create channel module spec")
                    return None
                module = importlib.util.module_from_spec(spec)
                module.__package__ = pkg_name  # enable relative imports
                sys.modules[channel_mod_name] = module
                spec.loader.exec_module(module)  # type: ignore[union-attr]
                logger.debug(f"[plugins] ({plugin.id}) Loaded as package: {pkg_name}")
                return module
            except Exception as e:  # noqa: BLE001
                logger.error(f"[plugins] ({plugin.id}) channel module import failed: {e}")
                if logger.isEnabledFor(10):
                    logger.debug("Traceback:\n%s", traceback.format_exc(limit=10))
                return None
        else:
            # --- Legacy file-path import (no __init__.py) ---
            spec_name = f"plugin_{plugin.id.replace('.', '_')}"
            logger.debug(f"[plugins] ({plugin.id}) Creating module spec name={spec_name}")
            spec = importlib.util.spec_from_file_location(spec_name, channel_file)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create module spec for {plugin.id}")
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec_name] = module
            logger.debug(f"[plugins] ({plugin.id}) Executing module spec")
            try:
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            except Exception as e:  # noqa: BLE001
                logger.error(f"[plugins] ({plugin.id}) Module execution failed: {e}")
                if logger.isEnabledFor(10):
                    logger.debug("Traceback:\n%s", traceback.format_exc(limit=10))
                return None
            return module

    def _find_channel_class(self, module: Any, plugin_id: str) -> type | None:
        """Find the appropriate channel class in the module"""
        # 1. Look for ChannelClass export (preferred)
        if hasattr(module, 'ChannelClass'):
            return module.ChannelClass

        # 2. Look for class with "Channel" in the name
        class_name = f'{plugin_id.split(".")[-1].title()}Channel'
        if hasattr(module, class_name):
            return getattr(module, class_name)

        # 3. Look for any class ending with "Channel"
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                attr_name.endswith('Channel') and
                attr.__module__ == module.__name__):
                return attr

        return None

    def _mount_static_assets(self, app: FastAPI, plugin: ChannelPlugin):
        """Mount static assets for the plugin"""
        try:
            # Mount UI directory if it exists
            ui_path = plugin.plugin_path / "ui"
            if ui_path.exists() and ui_path.is_dir():
                mount_path = f"/api/channels/{plugin.id}/ui"
                app.mount(mount_path, StaticFiles(directory=str(ui_path)), name=f"{plugin.id}-ui")
                logger.info(f"Mounted UI assets: {mount_path} -> {ui_path}")

            # Mount assets directory if it exists
            assets_path = plugin.plugin_path / "assets"
            if assets_path.exists() and assets_path.is_dir():
                mount_path = f"/api/channels/{plugin.id}/assets"
                app.mount(mount_path, StaticFiles(directory=str(assets_path)), name=f"{plugin.id}-assets")
                logger.info(f"Mounted assets: {mount_path} -> {assets_path}")

        except Exception as e:
            logger.error(f"Error mounting static assets for {plugin.id}: {e}")

    async def check_plugin_health(self, plugin: ChannelPlugin) -> bool:
        """Check if a plugin is healthy"""
        plugin.last_health_check = time.time()
        # For embedded plugins, health is determined by successful loading
        return plugin.healthy

    async def get_plugin_manifest(self, plugin_id: str) -> dict[str, Any] | None:
        """Get manifest from plugin instance"""
        plugin = self.plugins.get(plugin_id)
        if not plugin or not plugin.instance:
            return None

        try:
            # Try to get manifest from plugin instance
            if hasattr(plugin.instance, 'get_manifest'):
                return plugin.instance.get_manifest()

            # Fallback to basic manifest generation
            return {
                "id": plugin.id,
                "name": plugin.name,
                "description": plugin.description,
                "icon": plugin.icon,
                "imageEndpoints": [],  # Plugin should override this
                "uiComponent": f"/api/channels/{plugin.id}/ui/manage.esm.js",
                "staticAssets": f"/api/channels/{plugin.id}/assets"
            }

        except Exception as e:
            logger.error(f"Error getting manifest for {plugin_id}: {e}")
            return None

    async def request_plugin_image(self, plugin_id: str, request_data: dict[str, Any]) -> bytes | None:
        """Request image generation from plugin instance"""
        plugin = self.plugins.get(plugin_id)
        if not plugin or not plugin.instance:
            return None

        try:
            # Try to call image request method on plugin instance
            if hasattr(plugin.instance, 'request_image'):
                return await plugin.instance.request_image(request_data)

            logger.error(f"Plugin {plugin_id} does not support image requests")
            return None

        except Exception as e:
            logger.error(f"Error requesting image from {plugin_id}: {e}")
            return None

    def get_plugin(self, plugin_id: str) -> ChannelPlugin | None:
        """Get plugin by ID"""
        return self.plugins.get(plugin_id)

    def get_all_plugins(self) -> list[ChannelPlugin]:
        """Get all discovered plugins"""
        return list(self.plugins.values())

    def get_healthy_plugins(self) -> list[ChannelPlugin]:
        """Get only healthy plugins"""
        return [plugin for plugin in self.plugins.values() if plugin.healthy]

    async def load_single_plugin(self, plugin_path: Path, app: FastAPI) -> ChannelPlugin | None:
        """Load a single plugin at runtime (hot-reload).

        This follows the same logic as ``discover_plugins`` but targets a single
        directory.  Returns the ``ChannelPlugin`` instance on success, or ``None``
        if loading fails.
        """
        config_file = plugin_path / "plugin.json"
        if not config_file.exists():
            config_file = plugin_path / "config.json"
        if not config_file.exists():
            logger.error("[plugins] load_single_plugin: no config file in %s", plugin_path)
            return None

        plugin = await self._load_plugin_config(config_file, plugin_path)
        if not plugin:
            return None

        # Avoid loading duplicates
        if plugin.id in self.plugins:
            logger.warning("[plugins] Plugin %s already loaded – skipping", plugin.id)
            return self.plugins[plugin.id]

        await self._load_plugin_instance(plugin, app)
        self.plugins[plugin.id] = plugin
        logger.info("[plugins] Hot-loaded plugin: %s (healthy=%s)", plugin.id, plugin.healthy)
        return plugin

    async def unload_plugin(self, plugin_id: str, app: FastAPI) -> bool:
        """Unload a plugin: call shutdown hooks, remove routes/mounts, remove from registry.

        Returns True if the plugin was found and unloaded.
        """
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return False

        # Call shutdown lifecycle hooks on the instance
        inst = plugin.instance
        if inst:
            if hasattr(inst, "on_shutdown"):
                try:
                    result = inst.on_shutdown()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:  # noqa: BLE001
                    logger.warning("on_shutdown failed for %s during unload: %s", plugin_id, exc)
            if hasattr(inst, "stop"):
                try:
                    inst.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("stop() failed for %s during unload: %s", plugin_id, exc)

        # Remove plugin's API routes from the app
        mount_prefix = f"/api/channels/{plugin_id}"
        app.routes[:] = [
            r for r in app.routes
            if not (hasattr(r, "path") and str(getattr(r, "path", "")).startswith(mount_prefix))
        ]

        # Remove static mount points (StaticFiles mounts use app.routes with
        # mount names like "{plugin_id}-ui" and "{plugin_id}-assets")
        mount_names = {f"{plugin_id}-ui", f"{plugin_id}-assets"}
        app.routes[:] = [
            r for r in app.routes
            if not (hasattr(r, "name") and getattr(r, "name", None) in mount_names)
        ]

        # Clean up sys.modules entries for this plugin
        pkg_name = f"mimir_plugin_{plugin_id.replace('.', '_')}"
        legacy_name = f"plugin_{plugin_id.replace('.', '_')}"
        to_remove = [k for k in sys.modules if k == pkg_name or k.startswith(f"{pkg_name}.")
                      or k == legacy_name]
        for key in to_remove:
            del sys.modules[key]

        # Remove from registry
        del self.plugins[plugin_id]
        logger.info("[plugins] Unloaded plugin: %s", plugin_id)
        return True

    async def shutdown_plugins(self) -> None:
        """Call lifecycle shutdown hooks on all loaded plugins.

        Invokes ``on_shutdown`` (async) or ``stop`` (sync) if present,
        giving plugins a chance to persist state and release resources.
        """
        for plugin in self.plugins.values():
            if not plugin.instance:
                continue
            inst = plugin.instance
            # Prefer the new async on_shutdown hook
            if hasattr(inst, "on_shutdown"):
                try:
                    result = inst.on_shutdown()
                    if asyncio.iscoroutine(result):
                        await result
                    logger.info(f"Called on_shutdown for plugin {plugin.id}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"on_shutdown failed for {plugin.id}: {exc}")
            # Also call legacy stop() if present (e.g. Spotify push manager)
            if hasattr(inst, "stop"):
                try:
                    inst.stop()
                    logger.info(f"Called stop() for plugin {plugin.id}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"stop() failed for {plugin.id}: {exc}")


# Global service instance
plugin_discovery_service = PluginDiscoveryService()
