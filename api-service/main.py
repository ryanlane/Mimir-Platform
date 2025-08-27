"""
Mimir API Application Factory
Creates and configures the FastAPI application with modular architecture
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings

# Import infrastructure components
from app.db.base import engine
from app.core.logging import setup_logging, get_logger

# Import services
from app.services.channel_discovery import channel_discovery_service
from app.services.websocket import websocket_service
from app.services.distribution import distribution_service
from app.services.caching import cache_service

# Import routers
from app.api.routes.channels import router as channels_router
from app.api.routes.scenes import router as scenes_router
from app.api.routes.overlays import router as overlays_router
from app.api.routes.displays import router as displays_router
from app.api.routes.websockets import router as websockets_router
from app.api.routes.admin import health_router, admin_router


def _initialize_services(app: FastAPI, logger):
    """Initialize all services"""
    logger.info("Initializing services...")
    
    # Initialize channel discovery and discover channels
    discovered_channels = channel_discovery_service.discover_channels(app)
    logger.info(f"Discovered {len(discovered_channels)} channels")
    
    # Start distribution monitoring if enabled
    if settings.distribution_enabled:
        import asyncio
        asyncio.create_task(distribution_service.start_distribution_monitoring())
        logger.info("Distribution monitoring started")
    
    # Log service status
    capabilities = distribution_service.get_capability_flags()
    logger.info(f"Service capabilities: {capabilities}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"🚀 Mimir API v2.1.0 starting up...")
    print(f"📊 Database: {settings.database_url}")
    print(f"🌐 CORS Origins: {len(settings.cors_origins)} configured")
    print(f"📁 Channels Directory: {settings.channels_directory}")
    print(f"🔧 Debug Mode: {'enabled' if settings.debug else 'disabled'}")
    
    # Create database tables if they don't exist
    from app.db.base import engine
    from app.db.models import Base
    print("🗄️  Ensuring database schema exists...")
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("✅ Database schema ready")
    
    if settings.redis_enabled:
        print(f"🔴 Redis: enabled at {settings.redis_url}")
    
    if settings.distribution_enabled:
        print(f"📡 Distribution: enabled (mode: {settings.distribution_default_mode})")
    
    yield
    
    # Shutdown
    print("🛑 Mimir API shutting down...")


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
        lifespan=lifespan
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
    
    # Ensure database schema exists for clean installs
    logger.info("🗄️ Ensuring database schema exists...")
    from app.db.models import Base
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("✅ Database schema ready")
    
    # Database is managed by Alembic migrations
    # Run `alembic upgrade head` to ensure latest schema
    
    # Include routers
    app.include_router(health_router, prefix=settings.api_prefix, tags=["health"])
    app.include_router(channels_router, prefix=settings.api_prefix, tags=["channels"])
    app.include_router(scenes_router, prefix=settings.api_prefix, tags=["scenes"])
    app.include_router(overlays_router, prefix=settings.api_prefix, tags=["overlays"])
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
