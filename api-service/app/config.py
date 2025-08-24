"""
Configuration management for Mimir API
Implements environment-based configuration with validation
"""
import os


class Settings:
    """Application settings with environment variable support"""
    
    def __init__(self):
        # Database
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        self.database_pool_size = int(os.getenv("DATABASE_POOL_SIZE", "20"))
        self.database_max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "30"))
        self.database_pool_timeout = int(os.getenv("DATABASE_POOL_TIMEOUT", "60"))
        self.database_pool_recycle = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))
        self.database_pool_pre_ping = os.getenv("DATABASE_POOL_PRE_PING", "true").lower() == "true"
        
        # API
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "5000"))
        self.api_prefix = os.getenv("API_PREFIX", "/api")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Security
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://oak:3000,http://127.0.0.1:3000,http://oak,http://localhost,http://127.0.0.1")
        self.cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        
        # Channels
        self.channels_directory = os.getenv("CHANNELS_DIRECTORY", "channels")
        self.max_channel_instances = int(os.getenv("MAX_CHANNEL_INSTANCES", "50"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")
        
        # WebSocket
        self.websocket_ping_interval = int(os.getenv("WEBSOCKET_PING_INTERVAL", "20"))
        self.websocket_ping_timeout = int(os.getenv("WEBSOCKET_PING_TIMEOUT", "10"))


# Global settings instance
settings = Settings()
