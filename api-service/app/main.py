"""
Mimir API Application Factory
Creates and configures the FastAPI application with modular architecture
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings

# Import infrastructure components
from app.db.base import create_tables
from app.core.logging import setup_logging, get_logger

# Import routers
from app.api.routes.channels import router as channels_router
from app.api.routes.scenes import router as scenes_router
from app.api.routes.admin import health_router, admin_router


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
    
    # Create database tables (this will be replaced by Alembic migrations)
    create_tables()
    
    # Include routers
    app.include_router(health_router, prefix=settings.api_prefix, tags=["health"])
    app.include_router(channels_router, prefix=settings.api_prefix, tags=["channels"])
    app.include_router(scenes_router, prefix=settings.api_prefix, tags=["scenes"])
    app.include_router(admin_router, prefix=settings.api_prefix, tags=["admin"])
    
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
    
    if settings.redis_enabled:
        print(f"🔴 Redis: enabled at {settings.redis_url}")
    
    if settings.distribution_enabled:
        print(f"📡 Distribution: enabled (mode: {settings.distribution_default_mode})")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    print("🛑 Mimir API shutting down...")


# For backward compatibility, add basic WebSocket endpoint
# TODO: Move this to a dedicated WebSocket router in Phase 3
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """Basic WebSocket endpoint for backward compatibility"""
    # TODO: Implement using proper WebSocketManager service
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except Exception:
        pass


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
