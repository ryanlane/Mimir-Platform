"""
Mimir API Application Factory
Creates and configures the FastAPI application with modular architecture
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings

# Import infrastructure components
from app.db.base import engine
from app.core.logging import setup_logging, get_logger

# Import services
from app.services.channel_discovery import channel_discovery_service
from app.services.plugin_discovery import plugin_discovery_service
from app.services.websocket import websocket_service
from app.services.distribution import distribution_service
from app.services.caching import cache_service
from app.services.mdns_discovery import mdns_discovery_service

# Import routers
from app.api.routes.channels import router as channels_router
from app.api.routes.scenes import router as scenes_router
from app.api.routes.displays import router as displays_router
from app.api.routes.websockets import router as websockets_router
from app.api.routes.admin import health_router, admin_router


def _initialize_services(app: FastAPI, logger):
    """Initialize all services"""
    logger.info("Initializing services...")
    
    # Store the app reference for plugin discovery
    app.state.plugin_discovery_initialized = False
    
    # Start distribution monitoring if enabled
    if settings.distribution_enabled:
        import asyncio
        asyncio.create_task(distribution_service.start_distribution_monitoring())
        logger.info("Distribution monitoring started")
    
    # Start mDNS discovery service if enabled
    if settings.mdns_discovery_enabled:
        import asyncio
        asyncio.create_task(mdns_discovery_service.start_discovery())
        logger.info("mDNS discovery service started")
    
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
    
    # Create FastAPI app
    app = FastAPI(
        title="Mimir API",
        description="Multi-display content management system",
        version="2.1.0",
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize services
    _initialize_services(app, logger)
    
    # Database is managed by Alembic migrations
    # Run `alembic upgrade head` to ensure latest schema
    
    # Include routers
    app.include_router(health_router, prefix=settings.api_prefix, tags=["health"])
    app.include_router(channels_router, prefix=settings.api_prefix, tags=["channels"])
    app.include_router(scenes_router, prefix=settings.api_prefix, tags=["scenes"])
    app.include_router(displays_router, prefix=settings.api_prefix, tags=["displays"])
    app.include_router(admin_router, prefix=settings.api_prefix, tags=["admin"])
    
    # Include WebSocket routes (no prefix for WebSockets)
    app.include_router(websockets_router)
    
    # Mount static files for channels
    # TODO: This should be handled by the channel manager service
    try:
        app.mount("/channels", StaticFiles(directory=settings.channels_directory), name="channels")
    except RuntimeError as e:
        if settings.debug:
            print(f"Warning: Could not mount channels directory: {e}")
    
    return app


# Create app instance
app = create_app()


# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    print(f"🚀 Mimir API v2.1.0 starting up...")
    print(f"📊 Database: {settings.database_url}")
    print(f"🌐 CORS Origins: {len(settings.cors_origins)} configured")
    print(f"📁 Channels Directory: {settings.channels_directory}")
    print(f"🔧 Debug Mode: {'enabled' if settings.debug else 'disabled'}")
    
    # Initialize plugins
    await initialize_plugins(app)
    
    if settings.redis_enabled:
        print(f"🔴 Redis: enabled at {settings.redis_url}")
    
    if settings.distribution_enabled:
        print(f"📡 Distribution: enabled (mode: {settings.distribution_default_mode})")
    
    # Report mDNS discovery status
    if settings.mdns_discovery_enabled:
        if mdns_discovery_service.is_available:
            print(f"🔍 mDNS Discovery: enabled (continuous background monitoring)")
            print(f"   Auto-register: {settings.mdns_auto_register}")
            print(f"   Update interval: {settings.mdns_update_interval}s")
            print(f"   Offline timeout: {settings.mdns_offline_timeout}s")
        else:
            print(f"⚠️ mDNS Discovery: disabled (zeroconf library not available)")
    else:
        print(f"🔍 mDNS Discovery: disabled by configuration")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    print("🛑 Mimir API shutting down...")
    
    # Stop mDNS discovery service
    if settings.mdns_discovery_enabled:
        await mdns_discovery_service.stop_discovery()
        print("🔍 mDNS discovery service stopped")


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
