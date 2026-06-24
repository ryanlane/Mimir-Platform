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
Mimir API Application Factory
Creates and configures the FastAPI application with all necessary components and middleware.
"""
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.admin import admin_router, health_router
from app.api.routes.channels import router as channels_router
from app.api.routes.client_releases import router as client_releases_router
from app.api.routes.debug_mqtt import router as debug_mqtt_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.display_scene import router as display_scene_router
from app.api.routes.displays import router as displays_router
from app.api.routes.scenes import router as scenes_router
from app.api.routes.scheduler import router as scheduler_router
from app.api.routes.store import router as store_router
from app.api.routes.websockets import router as websockets_router
from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.metrics import metrics_app, metrics_middleware, setup_metrics
from app.core.scheduler import scheduler_service
from app.services.distribution import distribution_service
from app.services.mdns_discovery import mdns_discovery_service
from app.services.mqtt.presence import setup_mqtt_integration
from app.services.mqtt.publisher import (
    MQTTSceneAssignmentPublisher,
    setup_mqtt_scene_assignment,
)
from app.services.plugin_discovery import plugin_discovery_service
from app.services.scheduler_worker import SchedulerWorker


def _dev_lan_origin_regex() -> str | None:
    if not settings.debug:
        return None
    # Allow common private-network dev origins such as http://192.168.1.x:3000.
    return r"^https?://((localhost|127\.0\.0\.1)(:\d+)?|(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?)$"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown"""
    logger = get_logger("app.main")

    # Startup with green text
    if settings.debug:
        # ANSI escape code for green text
        green_text = "\033[92m🚀 Mimir API v2.1.0 starting up...\033[0m"
        print(green_text)  # Print directly to console with color

    logger.info("🚀 Mimir API v2.1.0 starting up...")  # Still log normally

    # Initialize core services
    setup_metrics()
    logger.info("📊 OpenTelemetry metrics initialized")

    # Setup and start scheduler
    if scheduler_service.setup_scheduler():
        await scheduler_service.start()
        logger.info("⏰ APScheduler started with background jobs")

        # Start scheduler worker for job execution
        app.state.scheduler_worker = SchedulerWorker()
        await app.state.scheduler_worker.start()
        logger.info("⚙️ Scheduler worker started for job execution")
    else:
        logger.warning("⚠️ APScheduler failed to initialize - using fallback mode")
        app.state.scheduler_worker = None

    # Initialize plugins (including dev channels)
    await initialize_plugins(app)

    # Start dev watcher for dev-linked channels
    from app.services.dev_watcher import dev_watcher_service
    dev_watcher_service.start(app)

    # Start shared HTML renderer (headless Chromium — used by any plugin that needs it)
    from app.services.html_renderer import html_renderer_service
    await html_renderer_service.start()
    if html_renderer_service.available:
        logger.info("🌐 HTML renderer: Chromium ready")
    else:
        logger.info("🌐 HTML renderer: unavailable (install playwright + chromium for HTML-based plugin styles)")

    # Report service status
    logger.info(f"📊 Database: {settings.database_url}")
    logger.info(f"🌐 CORS Origins: {len(settings.cors_origins)} configured")
    logger.info(f"📁 Channels Directory: {settings.channels_directory}")
    logger.info(f"🔧 Debug Mode: {'enabled' if settings.debug else 'disabled'}")

    if settings.redis_enabled:
        logger.info(f"🔴 Redis: enabled at {settings.redis_url}")

    if settings.distribution_enabled:
        logger.info(f"📡 Distribution: enabled (mode: {settings.distribution_default_mode})")

    # Report mDNS discovery status and start service
    if settings.mdns_discovery_enabled:
        if mdns_discovery_service.is_available:
            # Start mDNS discovery (now managed by scheduler)
            await mdns_discovery_service.start_discovery()
            logger.info("🔍 mDNS Discovery: enabled (continuous background monitoring)")
            logger.info(f"   Update interval: {settings.mdns_update_interval}s")
            logger.info(f"   Offline timeout: {settings.mdns_offline_timeout}s")
        else:
            logger.info("⚠️ mDNS Discovery: disabled (zeroconf library not available)")
    elif settings.mdns_external_feed_enabled:
        await mdns_discovery_service.start_external_feed()
        logger.info("🔍 mDNS Discovery: external feed mode enabled")
        logger.info(f"   Update interval: {settings.mdns_update_interval}s")
        logger.info(f"   Offline timeout: {settings.mdns_offline_timeout}s")
    else:
        logger.info("🔍 mDNS Discovery: disabled by configuration")

    # Setup MQTT presence detection for instant online/offline
    if settings.mqtt_enabled:
        mqtt_success = await setup_mqtt_integration()
        # Also bring up the scene listener + publisher
        await setup_mqtt_scene_assignment()
        MQTTSceneAssignmentPublisher.initialize(client_id="mimir-scenes")
        # Start discovery registry sweeper (hybrid Redis) if enabled
        if getattr(settings, "mqtt_discovery_enabled", False):
            try:
                from app.services.mqtt.discovery_registry import mqtt_discovery_registry
                await mqtt_discovery_registry.start()
                logger.info("🔍 MQTT discovery registry started (hybrid Redis)")
            except Exception as e:  # pragma: no cover
                logger.warning(f"Failed to start discovery registry: {e}")
        # Start short-code pairing service
        try:
            from app.services.mqtt.pairing import pairing_service
            await pairing_service.start()
            logger.info("🔗 Pairing service started (short-code / QR registration)")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Failed to start pairing service: {e}")
        # Eagerly start the async publisher loop so the first refresh does not race the lazy start
        try:  # defensive – publisher start should not block overall startup
            publisher_instance = MQTTSceneAssignmentPublisher.get()
            await publisher_instance.start()
            logger.info("📡 MQTT Scene assignment publisher started (eager)")
        except Exception as e:  # pragma: no cover – startup resilience
            logger.warning("⚠️ Failed to eagerly start MQTT scene assignment publisher: %s", e)
        # Fleet OTA rollout controller (Phase 3): retained desired_version topic
        try:
            from app.services.fleet_rollout import fleet_rollout_service
            await fleet_rollout_service.start()
            logger.info("🚀 Fleet rollout controller started")
        except Exception as e:  # pragma: no cover – startup resilience
            logger.warning("⚠️ Failed to start fleet rollout controller: %s", e)

        if mqtt_success:
            logger.info(f"📡 MQTT Presence: enabled at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
            logger.info("   Instant online/offline detection via Last Will & Testament")
        else:
            logger.warning(f"⚠️ MQTT Presence: failed to connect to {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
    else:
        logger.info("📡 MQTT Services: disabled by configuration")

    # Log service capabilities
    capabilities = distribution_service.get_capability_flags()
    logger.info(f"🔧 Service capabilities: {capabilities}")

    yield

    # Shutdown
    logger.info("🛑 Mimir API shutting down...")

    # Stop dev watcher first (before unloading plugins)
    from app.services.dev_watcher import dev_watcher_service
    dev_watcher_service.stop()

    # Stop shared HTML renderer
    from app.services.html_renderer import html_renderer_service
    await html_renderer_service.stop()

    # Shutdown plugins (lifecycle hooks + legacy stop)
    await plugin_discovery_service.shutdown_plugins()
    logger.info("🔌 Plugin shutdown complete")

    # Stop scheduler worker
    if hasattr(app.state, 'scheduler_worker') and app.state.scheduler_worker:
        await app.state.scheduler_worker.stop()
        logger.info("⚙️ Scheduler worker stopped")

    # Stop MQTT services
    if settings.mqtt_enabled:
        logger.info("📝 MQTT services stopped")

    # Stop mDNS discovery service
    if settings.mdns_discovery_enabled:
        await mdns_discovery_service.stop_discovery()
        logger.info("🔍 mDNS discovery service stopped")

    # Stop scheduler
    await scheduler_service.stop()
    logger.info("⏰ APScheduler stopped")


def _initialize_services(app: FastAPI, logger):
    """Initialize all services (now using modern scheduler approach)"""
    logger.info("Initializing services...")

    # Store the app reference for plugin discovery
    app.state.plugin_discovery_initialized = False

    # Note: Background jobs are now managed by APScheduler in the lifespan function
    # The old asyncio.create_task() calls have been replaced with scheduled jobs

    # Log service status
    capabilities = distribution_service.get_capability_flags()
    logger.info(f"Service capabilities: {capabilities}")


async def initialize_plugins(app: FastAPI):
    """Initialize plugins during startup event"""
    if hasattr(app.state, 'plugin_discovery_initialized') and app.state.plugin_discovery_initialized:
        return

    print("🔍 Starting plugin discovery...")
    try:
        discovered_plugins = await plugin_discovery_service.discover_plugins(app)
        print(f"🔌 Plugins discovered: {len(discovered_plugins)} channel plugins loaded")
        for plugin in discovered_plugins:
            print(f"   - {plugin.id}: {plugin.name}")
        app.state.plugin_discovery_initialized = True
    except Exception as e:
        print(f"❌ Plugin discovery failed: {e}")
        import traceback
        traceback.print_exc()

    # Load dev-linked channels (if any)
    try:
        from app.services.plugin_manager import plugin_manager_service
        await plugin_manager_service.load_dev_channels_on_startup(app)
    except Exception as e:
        print(f"⚠️ Dev channel loading failed: {e}")


def create_app() -> FastAPI:
    """Application factory function"""

    # Setup logging first
    setup_logging()
    logger = get_logger("app.main")

    # Create FastAPI app with lifespan management
    app = FastAPI(
        title="Mimir API",
        description="Multi-display content management system",
        version="2.1.0",
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )

    # Add root endpoint for health check or landing page
    @app.get("/")
    async def root():
        """Root endpoint for service status."""
        return {"message": "Mimir API is running"}

    # Add metrics middleware for automatic HTTP request instrumentation
    app.middleware("http")(metrics_middleware)

    # Middleware: Guard against accidental base64 image blobs used as URL paths
    # Root cause: legacy/incorrect clients sometimes take a raw base64 image (e.g. JPEG starting with /9j/)
    # and place it directly in an <img src="/..."> attribute, generating huge invalid GET paths like
    #   /9j/4AAQSkZJRgABAQAAAQABAAD... (potentially thousands of chars) which previously produced 500s.
    # We detect these patterns early and return a concise 400 with guidance, suppressing log spam.
    base64_path_seen: dict[str, int] = {}

    BASE64_SIGNATURE_PREFIXES = (
        "9j/4AAQ",        # JPEG
        "iVBORw0K",       # PNG
        "R0lGOD",         # GIF (GIF87a/89a)
        "PHN2Zy",         # <svg ("<svg" base64)
    )

    allowed_route_prefixes = ("/api/", "/static/", "/channels/", "/docs", "/redoc", "/metrics")
    base64_chars_pattern = re.compile(r"^[A-Za-z0-9+/=%]{40,}$")  # long run of base64-ish chars

    @app.middleware("http")
    async def base64_path_guard(request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        # Allow known prefixes fast
        if path == "/" or path.startswith(allowed_route_prefixes):
            return await call_next(request)

        trimmed = path.lstrip('/')

        # Strategy:
        # 1. Combine early path segments (because raw base64 contains '/') until threshold length.
        # 2. Remove '/' to evaluate continuous base64 signature.
        # 3. Check signature + character set + length.
        segments = [s for s in trimmed.split('/') if s]
        if not segments:
            return await call_next(request)

        candidate_parts = []
        total_len = 0
        for seg in segments:
            candidate_parts.append(seg)
            total_len += len(seg)
            if total_len >= 80 or len(candidate_parts) >= 6:
                break
        candidate_joined = ''.join(candidate_parts)

        # Only proceed if overall path length large enough to be suspicious and candidate looks like start of base64 image
        if total_len >= 60:
            # Normalize for signature test
            for sig in BASE64_SIGNATURE_PREFIXES:
                if candidate_joined.startswith(sig):
                    # Validate base64-ish char run (tolerate up to 10% non-base64 chars in first 200)
                    sample = candidate_joined[:200]
                    invalid = sum(1 for c in sample if c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
                    if invalid / max(1, len(sample)) <= 0.1 and base64_chars_pattern.match(sample):
                        prefix_key = candidate_joined[:16]
                        count = base64_path_seen.get(prefix_key, 0) + 1
                        base64_path_seen[prefix_key] = count
                        client_host = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
                        if count <= 3:
                            get_logger("app.security").warning(
                                "Blocked probable misused multi-segment base64 path (count=%s, client=%s, prefix=%s...) total_len=%s segments=%s", count, client_host, prefix_key, total_len, len(candidate_parts)
                            )
                        return JSONResponse(status_code=400, content={
                            "detail": "Probable misused base64 image requested as URL path. Use provided imageUrl or a data URI instead.",
                            "error": "base64_path_misuse",
                            "length": len(trimmed),
                        })
                    break  # signature matched even if failed deeper test

        return await call_next(request)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=_dev_lan_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize services

    # Database is managed by Alembic migrations
    # Run `alembic upgrade head` to ensure latest schema

    # Include routers
    app.include_router(health_router, prefix=settings.api_prefix, tags=["health"])
    app.include_router(channels_router, prefix=settings.api_prefix, tags=["channels"])
    app.include_router(scenes_router, prefix=settings.api_prefix, tags=["scenes"])
    app.include_router(displays_router, prefix=settings.api_prefix, tags=["displays"])
    # Discovery (new) under same /displays namespace
    app.include_router(discovery_router, prefix=settings.api_prefix, tags=["discovery"])
    app.include_router(display_scene_router, prefix=settings.api_prefix, tags=["display-scene"])
    app.include_router(scheduler_router, prefix=settings.api_prefix, tags=["scheduler"])
    app.include_router(admin_router, prefix=settings.api_prefix, tags=["admin"])
    app.include_router(client_releases_router, prefix=settings.api_prefix, tags=["client-releases"])
    app.include_router(store_router, prefix=settings.api_prefix, tags=["store"])

    # Include WebSocket routes (no prefix for WebSockets)
    app.include_router(websockets_router)
    app.include_router(debug_mqtt_router, prefix=f"{settings.api_prefix}")

    # Mount Prometheus metrics endpoint for observability
    try:
        app.mount("/metrics", metrics_app, name="metrics")
        logger.info("📊 OpenTelemetry metrics endpoint mounted at /metrics")
    except Exception as e:
        logger.warning(f"Failed to mount metrics endpoint: {e}")

    # Mount static files for channels
    # TODO: This should be handled by the channel manager service
    try:
        app.mount("/channels", StaticFiles(directory=settings.channels_directory), name="channels")
    except RuntimeError as e:
        if settings.debug:
            print(f"Warning: Could not mount channels directory: {e}")

    # Mount media directory (display images + swap space) at /media
    try:
        from pathlib import Path
        media_root_cfg = getattr(settings, "display_images_directory", "display_images")
        media_root = Path(media_root_cfg)
        if not media_root.is_absolute():
            # Resolve relative media dir under upload_dir (consistent with persistence service)
            from pathlib import Path as _P
            try:
                upload_base = _P(getattr(settings, "upload_dir", ".")).resolve()
            except Exception:  # noqa: BLE001
                upload_base = _P.cwd()
            media_root = (upload_base / media_root).resolve()
        media_root.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=str(media_root)), name="media")
        logger.info(f"📁 Media files mounted at /media root={media_root}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to mount media directory: {e}")

    # Mount static files for general content (test images, etc.)
    try:
        import os
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
            logger.info("📁 Static files mounted at /static")
        else:
            logger.warning(f"Static directory not found: {static_dir}")
    except Exception as e:
        logger.warning(f"Failed to mount static files: {e}")

    return app


# Create app instance
app = create_app()


# Development server entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
    log_level=settings.log_level.lower()

