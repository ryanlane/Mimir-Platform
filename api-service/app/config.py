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
    # Directory where scheduler-generated (transient) images are first written before being
    # optionally copied/mirrored into the public channels directory for serving.
    scheduler_temp_directory: str = Field(
        default="scheduler_temp",
        validation_alias=AliasChoices("SCHEDULER_TEMP", "SCHEDULER_TEMP_DIR"),
    )
    api_prefix: str = Field("/api", validation_alias="API_PREFIX")
    api_host: str = Field("0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(5000, validation_alias="API_PORT")
    debug: bool = Field(False, validation_alias="DEBUG")

    # --- Public URL (used in payloads sent to remote display clients) ---
    # If not provided, falls back to mqtt_broker_host + api_port.
    public_scheme: str = Field("http", validation_alias=AliasChoices("PUBLIC_SCHEME", "API_PUBLIC_SCHEME"))
    public_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_HOST", "API_PUBLIC_HOST", "EXTERNAL_HOST"),
    )
    public_port: int | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_PORT", "API_PUBLIC_PORT", "EXTERNAL_PORT"),
    )

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

    # --- mDNS Discovery ---
    mdns_discovery_enabled: bool = Field(True, validation_alias=AliasChoices("MDNS_DISCOVERY_ENABLED", "MDNS_ENABLED"))
    mdns_update_interval: int = Field(30, validation_alias=AliasChoices("MDNS_UPDATE_INTERVAL",))  # seconds
    mdns_offline_timeout: int = Field(120, validation_alias=AliasChoices("MDNS_OFFLINE_TIMEOUT",))  # seconds

    # --- MQTT Presence (for instant online/offline detection) ---
    mqtt_enabled: bool = Field(True, validation_alias=AliasChoices("MQTT_ENABLED",))
    mqtt_broker_host: str = Field("oak", validation_alias=AliasChoices("MQTT_BROKER_HOST", "MQTT_HOST"))
    mqtt_broker_port: int = Field(1883, validation_alias=AliasChoices("MQTT_BROKER_PORT", "MQTT_PORT"))
    mqtt_username: str | None = Field(default=None, validation_alias=AliasChoices("MQTT_USERNAME", "MQTT_USER"))
    mqtt_password: str | None = Field(default=None, validation_alias=AliasChoices("MQTT_PASSWORD", "MQTT_PASS"))
    mqtt_client_id_prefix: str = Field("mimir", validation_alias=AliasChoices("MQTT_CLIENT_ID_PREFIX",))

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

    @property
    def public_base_url(self) -> str:
        """Derive a base URL suitable for remote display clients without extra env config.

        Resolution strategy (first successful wins):
        1. Explicit public_host (env override)
        2. mqtt_broker_host (often already a LAN-resolvable hostname)
        3. Local system hostname (socket.gethostname())
        4. hostname + ".local" (for mDNS-capable environments)
        5. Primary outbound IPv4 (UDP connect probe)
        6. Fallback 127.0.0.1 (last resort)

        Ports: omit when standard (80 http / 443 https). This avoids confusing some
        embedded HTTP clients that mishandle explicit default ports.
        """
        import socket

        scheme = self.public_scheme or "http"

        # Helper to test if host resolves to at least one non-loopback address
        def _host_resolves(candidate: str | None) -> bool:
            if not candidate:
                return False
            try:
                infos = socket.getaddrinfo(candidate, None)
            except Exception:
                return False
            for _family, _type, _proto, _canon, sockaddr in infos:
                ip = sockaddr[0]
                if not (ip.startswith("127.") or ip in ("::1",)):
                    return True
            return False

        # Candidate hostnames in priority order (deduplicated later)
        hostname = socket.gethostname()
        candidates: list[str | None] = [
            self.public_host,
            self.mqtt_broker_host,
            hostname,
            f"{hostname}.local",
        ]

        seen = set()
        chosen_host: str | None = None
        for cand in candidates:
            if not cand or cand in seen:
                continue
            seen.add(cand)
            if _host_resolves(cand):
                chosen_host = cand
                break

        if chosen_host is None:
            # Derive primary outbound IP (does not create traffic, just local routing decision)
            ip = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))  # any public IP works; no packets sent until write
                ip = s.getsockname()[0]
                s.close()
            except Exception:
                pass
            chosen_host = ip or "127.0.0.1"

        port = self.public_port if self.public_port is not None else self.api_port
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            return f"{scheme}://{chosen_host}"
        return f"{scheme}://{chosen_host}:{port}"

settings = Settings()
