"""
Configuration management for Mimir API
Implements environment-based configuration with Pydantic Settings validation
"""
import os
from typing import List

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Fallback for when pydantic-settings is not installed
    class BaseSettings:
        pass
    def Field(**kwargs):
        return kwargs.get('default')


class Settings(BaseSettings if PYDANTIC_AVAILABLE else object):
    """Application settings with environment variable support and validation"""
    
    def __init__(self):
        if not PYDANTIC_AVAILABLE:
            # Fallback to environment variables
            self._init_from_env()
        else:
            super().__init__()
    
    def _init_from_env(self):
        """Initialize settings from environment variables (fallback)"""
        # Database Configuration
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        self.database_pool_size = int(os.getenv("DATABASE_POOL_SIZE", "20"))
        self.database_max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "30"))
        self.database_pool_timeout = int(os.getenv("DATABASE_POOL_TIMEOUT", "60"))
        self.database_pool_recycle = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))
        self.database_pool_pre_ping = os.getenv("DATABASE_POOL_PRE_PING", "true").lower() == "true"
        
        # API Configuration
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "5000"))
        self.api_prefix = os.getenv("API_PREFIX", "/api")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Security Configuration
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://oak:3000,http://127.0.0.1:3000,http://oak,http://localhost,http://127.0.0.1")
        self.cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        
        # Channels Configuration
        self.channels_directory = os.getenv("CHANNELS_DIRECTORY", "channels")
        self.max_channel_instances = int(os.getenv("MAX_CHANNEL_INSTANCES", "50"))
        
        # Logging Configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")
        
        # WebSocket Configuration
        self.websocket_ping_interval = int(os.getenv("WEBSOCKET_PING_INTERVAL", "20"))
        self.websocket_ping_timeout = int(os.getenv("WEBSOCKET_PING_TIMEOUT", "10"))
        
        # Redis Configuration (optional)
        self.redis_enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        
        # Distribution Configuration
        self.distribution_enabled = os.getenv("DISTRIBUTION_ENABLED", "false").lower() == "true"
        self.distribution_default_mode = os.getenv("DISTRIBUTION_DEFAULT_MODE", "MIRROR")
        
        # Feature Flags
        self.enable_metrics = os.getenv("ENABLE_METRICS", "false").lower() == "true"
        self.enable_tracing = os.getenv("ENABLE_TRACING", "false").lower() == "true"


if PYDANTIC_AVAILABLE:
    # Pydantic-based settings with validation
    class Settings(BaseSettings):
        """Application settings with environment variable support and validation"""
        
        # Database Configuration
        database_url: str = Field(default="sqlite:///./app.db", description="Database URL")
        database_pool_size: int = Field(default=20, description="Database connection pool size")
        database_max_overflow: int = Field(default=30, description="Database max overflow connections")
        database_pool_timeout: int = Field(default=60, description="Database pool timeout in seconds")
        database_pool_recycle: int = Field(default=3600, description="Database pool recycle time in seconds")
        database_pool_pre_ping: bool = Field(default=True, description="Enable database pool pre-ping")
        
        # API Configuration
        api_host: str = Field(default="0.0.0.0", description="API host")
        api_port: int = Field(default=5000, description="API port")
        api_prefix: str = Field(default="/api", description="API prefix")
        debug: bool = Field(default=False, description="Enable debug mode")
        
        # Security Configuration
        secret_key: str = Field(
            default="your-secret-key-change-in-production", 
            description="Secret key for signing tokens"
        )
        cors_origins: List[str] = Field(
            default=[
                "http://localhost:3000",
                "http://oak:3000", 
                "http://127.0.0.1:3000",
                "http://oak",
                "http://localhost",
                "http://127.0.0.1"
            ],
            description="CORS allowed origins"
        )
        rate_limit_requests: int = Field(default=100, description="Rate limit requests per window")
        rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")
        
        # Channels Configuration
        channels_directory: str = Field(default="channels", description="Channels directory path")
        channels_dir: str = Field(default="channels", description="Alternative channels directory path")
        max_channel_instances: int = Field(default=50, description="Maximum channel instances")
        
        # Logging Configuration
        log_level: str = Field(default="INFO", description="Logging level")
        log_format: str = Field(default="json", description="Log format (json or text)")
        log_file: str = Field(default="", description="Log file path")
        
        # WebSocket Configuration
        websocket_ping_interval: int = Field(default=20, description="WebSocket ping interval in seconds")
        websocket_ping_timeout: int = Field(default=10, description="WebSocket ping timeout in seconds")
        
        # Redis Configuration (optional)
        redis_enabled: bool = Field(default=False, description="Enable Redis for caching and distribution")
        redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
        redis_host: str = Field(default="localhost", description="Redis host")
        redis_port: int = Field(default=6379, description="Redis port")
        redis_db: int = Field(default=0, description="Redis database number")
        
        # Database Pool Configuration (alternative field names)
        pool_size: int = Field(default=20, description="Database connection pool size (alt name)")
        max_overflow: int = Field(default=30, description="Database max overflow connections (alt name)")
        pool_timeout: int = Field(default=60, description="Database pool timeout in seconds (alt name)")
        pool_recycle: int = Field(default=3600, description="Database pool recycle time in seconds (alt name)")
        
        # Health Checks
        enable_health_checks: bool = Field(default=True, description="Enable health check endpoints")
        
        # Distribution Configuration
        distribution_enabled: bool = Field(default=False, description="Enable content distribution features")
        distribution_default_mode: str = Field(default="MIRROR", description="Default distribution mode")
        
        # Feature Flags
        enable_metrics: bool = Field(default=False, description="Enable Prometheus metrics")
        enable_tracing: bool = Field(default=False, description="Enable request tracing")
        
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False
            extra = "ignore"  # Allow extra fields without validation errors


# Global settings instance
settings = Settings()
