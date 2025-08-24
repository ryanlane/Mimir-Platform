"""
Mimir API Application Factory
Creates and configures the FastAPI application with modular architecture
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.infrastructure.database.connection import create_tables
from app.api.routes.channels import router as channels_router
from app.api.routes.scenes import router as scenes_router
from app.api.routes.admin import health_router, admin_router


def create_app() -> FastAPI:
    """Application factory function"""
    
    # Create FastAPI app
    app = FastAPI(
        title="Mimir API",
        description="Multi-display content management system",
        version="2.1.0",
        debug=settings.debug
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Create database tables
    create_tables()
    
    # Include routers
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(channels_router, prefix=settings.api_prefix)
    app.include_router(scenes_router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    
    # Mount static files for channels
    # TODO: This should be handled by the channel manager
    # app.mount("/channels", StaticFiles(directory="channels"), name="channels")
    
    return app


# Create app instance
app = create_app()


# Add any additional startup events
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    print(f"🚀 Mimir API starting up...")
    print(f"📊 Database URL: {settings.database_url}")
    print(f"🌐 CORS Origins: {settings.cors_origins}")
    print(f"📁 Channels Directory: {settings.channels_directory}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    print("🛑 Mimir API shutting down...")


# For backward compatibility, we'll add a simple WebSocket endpoint
# TODO: Move this to a dedicated WebSocket router
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """Basic WebSocket endpoint for backward compatibility"""
    # TODO: Implement using WebSocketManager
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
