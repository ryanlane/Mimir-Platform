"""
Mimir API Application Factory
Creates and configures the FastAPI application with all necessary components and middleware.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings

# Import infrastructure components
from app.db.base import engine
from app.core.logging import setup_logging, get_logger
from app.core.metrics import setup_metrics, metrics_middleware, metrics_app
from app.core.scheduler import scheduler_service

# Import services
from app.services.channel_discovery import channel_discovery_service
from app.services.plugin_discovery import plugin_discovery_service
from app.services.websocket import websocket_service
from app.services.distribution import distribution_service
from app.services.caching import cache_service
from app.services.mdns_discovery import mdns_discovery_service
from app.services.mqtt_presence import mqtt_presence_service, setup_mqtt_integration
from app.services.mqtt_registration import auto_registration_service, setup_auto_registration, cleanup_auto_registration
from app.services.mqtt_scene_assignment import mqtt_scene_service, setup_mqtt_scene_assignment

# Import routers
from app.api.routes.channels import router as channels_router
from app.api.routes.scenes import router as scenes_router
from app.api.routes.displays import router as displays_router
from app.api.routes.display_scene import router as display_scene_router
from app.api.routes.discovered_displays import router as discovered_displays_router
from app.api.routes.websockets import router as websockets_router
from app.api.routes.admin import health_router, admin_router


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
    else:
        logger.warning("⚠️ APScheduler failed to initialize - using fallback mode")
    
    # Initialize plugins
    await initialize_plugins(app)
    
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
            logger.info(f"🔍 mDNS Discovery: enabled (continuous background monitoring)")
            logger.info(f"   Update interval: {settings.mdns_update_interval}s")
            logger.info(f"   Offline timeout: {settings.mdns_offline_timeout}s")
        else:
            logger.info(f"⚠️ mDNS Discovery: disabled (zeroconf library not available)")
    else:
        logger.info(f"🔍 mDNS Discovery: disabled by configuration")
    
    # Setup MQTT presence detection for instant online/offline
    if settings.mqtt_enabled:
        mqtt_success = await setup_mqtt_integration()
        auto_reg_success = await setup_auto_registration()
        scene_success = await setup_mqtt_scene_assignment()
        
        if mqtt_success:
            logger.info(f"📡 MQTT Presence: enabled at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
            logger.info(f"   Instant online/offline detection via Last Will & Testament")
        else:
            logger.warning(f"⚠️ MQTT Presence: failed to connect to {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
        
        if auto_reg_success:
            logger.info(f"🔄 Auto-Registration: enabled - mDNS discovery → MQTT registration")
            logger.info(f"   Automatic display registration and test image workflow")
            
            # Connect auto-registration to mDNS discovery
            mdns_discovery_service.add_discovery_callback(auto_registration_service.handle_discovered_display)
        else:
            logger.warning(f"⚠️ Auto-Registration: failed to start")
        
        if scene_success:
            logger.info(f"🎬 MQTT Scene Assignment: enabled - listening on mimir/+/evt")
            logger.info(f"   Pure MQTT scene assignment workflow available")
        else:
            logger.warning(f"⚠️ MQTT Scene Assignment: failed to start")
    else:
        logger.info(f"📡 MQTT Services: disabled by configuration")
    
    # Log service capabilities
    capabilities = distribution_service.get_capability_flags()
    logger.info(f"🔧 Service capabilities: {capabilities}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Mimir API shutting down...")
    
    # Stop MQTT services
    if settings.mqtt_enabled:
        await mqtt_scene_service.stop()
        await cleanup_auto_registration()
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
    
    # Add metrics middleware for automatic HTTP request instrumentation
    app.middleware("http")(metrics_middleware)
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
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
    app.include_router(display_scene_router, prefix=settings.api_prefix, tags=["display-scene"])
    app.include_router(discovered_displays_router, prefix=settings.api_prefix, tags=["discovered-displays"])
    app.include_router(admin_router, prefix=settings.api_prefix, tags=["admin"])
    
    # Include WebSocket routes (no prefix for WebSockets)
    app.include_router(websockets_router)
    
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
    
    # Mount static files for general content (test images, etc.)
    try:
        import os
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
        if os.path.exists(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
            logger.info(f"📁 Static files mounted at /static")
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
