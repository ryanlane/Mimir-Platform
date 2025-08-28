# app/config.py
from __future__ import annotations

from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # --- Database ---
    database_url: str = Field(
        default="sqlite:///./app.db",
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL"),
    )
    database_pool_size: int = Field(5, validation_alias=AliasChoices("DB_POOL_SIZE", "DATABASE_POOL_SIZE"))
    database_max_overflow: int = Field(10, validation_alias=AliasChoices("DB_MAX_OVERFLOW", "DATABASE_MAX_OVERFLOW", "DB_POOL_MAX_OVERFLOW"))
    database_pool_timeout: int = Field(30, validation_alias=AliasChoices("DB_POOL_TIMEOUT", "DATABASE_POOL_TIMEOUT"))
    database_pool_recycle: int = Field(1800, validation_alias=AliasChoices("DB_POOL_RECYCLE", "DATABASE_POOL_RECYCLE"))
    database_pool_pre_ping: bool = Field(True, validation_alias=AliasChoices("DB_POOL_PRE_PING", "DATABASE_POOL_PRE_PING"))

    # --- Paths / service ---
    channels_directory: str = Field(
        default="channels",
        validation_alias=AliasChoices("CHANNELS_DIR", "CHANNELS_DIRECTORY"),
    )
    upload_dir: str = Field(
        default="/var/opt/mimir/mimir-api/uploads",
        validation_alias="UPLOAD_DIR",
    )
    api_prefix: str = Field("/api", validation_alias="API_PREFIX")
    api_host: str = Field("0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(5000, validation_alias="API_PORT")
    debug: bool = Field(False, validation_alias="DEBUG")

    # --- Security / CORS ---
    secret_key: str = Field("change-me", validation_alias=AliasChoices("SECRET_KEY","JWT_SECRET","APP_SECRET"))
    cors_origins: list[str] = Field(default_factory=list, validation_alias=AliasChoices("CORS_ORIGINS","CORS_ALLOW_ORIGINS"))

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        # Accept list, JSON, or comma-separated string
        if v is None or v == "":
            return []
        if isinstance(v, (list, tuple)):
            return list(v)
        s = str(v).strip()
        if s.startswith("["):
            # JSON-like list
            import json
            try:
                return json.loads(s)
            except Exception:
                pass
        return [item.strip() for item in s.split(",") if item.strip()]

    # --- Logging ---
    log_level: str = Field("INFO", validation_alias=AliasChoices("LOG_LEVEL", "UVICORN_LOG_LEVEL"))
    log_format: str = Field("plain", validation_alias=AliasChoices("LOG_FORMAT",))  # "plain" or "json"

    # --- Redis (optional) ---
    # If REDIS_ENABLED=false (default), your app should skip initializing Redis.
    redis_enabled: bool = Field(False, validation_alias=AliasChoices("REDIS_ENABLED",))
    redis_url: str | None = Field(default=None, validation_alias=AliasChoices("REDIS_URL",))
    redis_host: str = Field("127.0.0.1", validation_alias=AliasChoices("REDIS_HOST",))
    redis_port: int = Field(6379, validation_alias=AliasChoices("REDIS_PORT",))
    redis_db: int = Field(0, validation_alias=AliasChoices("REDIS_DB",))
    redis_password: str | None = Field(default=None, validation_alias=AliasChoices("REDIS_PASSWORD",))
    redis_ssl: bool = Field(False, validation_alias=AliasChoices("REDIS_SSL",))

    # --- Distribution (Redis-based) ---
    distribution_default_mode: str = Field("MIRROR", validation_alias=AliasChoices("DISTRIBUTION_DEFAULT_MODE",))

    @property
    def redis_dsn(self) -> str | None:
        """Build a Redis URL when REDIS_URL isn't provided."""
        if not self.redis_enabled:
            return None
        if self.redis_url:
            return self.redis_url
        scheme = "rediss" if self.redis_ssl else "redis"
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"{scheme}://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def distribution_enabled(self) -> bool:
        """Distribution features are enabled when Redis is enabled."""
        return self.redis_enabled

settings = Settings()
