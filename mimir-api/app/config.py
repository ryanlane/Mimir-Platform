# app/config.py
from __future__ import annotations

import re
import socket

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Notes:
        - `cors_origins_raw` is kept as a raw string to avoid pydantic's early JSON parsing.
        - `cors_origins` is derived in a model-level validator so we can reliably
          inspect the already-normalized raw value regardless of field ordering.
    """

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
    client_releases_dir: str = Field(
        default="/var/opt/mimir/mimir-api/client-releases",
        validation_alias="CLIENT_RELEASES_DIR",
        description="Directory of cached mimir-display release artifacts (populated by mimir-update.sh).",
    )
    # Directory where scheduler-generated (transient) images are first written before being
    # optionally copied/mirrored into the public channels directory for serving.
    scheduler_temp_directory: str = Field(
        default="scheduler_temp",
        validation_alias=AliasChoices("SCHEDULER_TEMP", "SCHEDULER_TEMP_DIR"),
    )
    scheduler_temp_max_age_minutes: int = Field(
        1440,
        validation_alias=AliasChoices("SCHEDULER_TEMP_MAX_AGE_MINUTES", "SCHEDULER_TEMP_RETENTION_MIN"),
        description="Retention window for scheduler temp images (minutes).",
    )
    # Directory for persisted display images & thumbnails (may be overridden for writable volume)
    display_images_directory: str = Field(
        "display_images",
        validation_alias=AliasChoices("DISPLAY_IMAGES_DIR", "DISPLAY_IMAGES_DIRECTORY"),
        description="Directory (absolute or relative). Relative paths are resolved under UPLOAD_DIR for persisted display scene images.",
    )
    # Persisted display image retention (database rows + local copies)
    display_image_retention_enabled: bool = Field(
        True,
        validation_alias=AliasChoices(
            "DISPLAY_IMAGE_RETENTION_ENABLED",
            "DISPLAY_LAST_IMAGE_RETENTION_ENABLED",
        ),
        description="Enable periodic pruning of persisted display scene images",
    )
    display_image_retention_max_per_pair: int = Field(
        10,
        validation_alias=AliasChoices(
            "DISPLAY_IMAGE_RETENTION_MAX_PER_PAIR",
            "DISPLAY_LAST_IMAGE_MAX_PER_PAIR",
        ),
        description="Max persisted rows to keep per (display, scene, subchannel) pair.",
    )
    display_image_retention_interval_seconds: int = Field(
        600,
        validation_alias=AliasChoices(
            "DISPLAY_IMAGE_RETENTION_INTERVAL_SECONDS",
            "DISPLAY_LAST_IMAGE_RETENTION_INTERVAL_SECONDS",
        ),
        description="Interval between retention prune passes (seconds).",
    )
    # --- Swap (ephemeral per-display image) controls ---
    display_swap_enabled: bool = Field(
        True,
        validation_alias=AliasChoices("DISPLAY_SWAP_ENABLED", "IMAGE_SWAP_ENABLED"),
        description="Enable per-display swap file writing for distributed images.",
    )
    display_swap_max_files_per_display: int = Field(
        25,
        validation_alias=AliasChoices("DISPLAY_SWAP_MAX_FILES_PER_DISPLAY", "IMAGE_SWAP_MAX_PER_DISPLAY"),
        description="Retention cap for swap images per (scene,display) pair.",
    )
    display_swap_prune_on_cleanup: bool = Field(
        True,
        validation_alias=AliasChoices("DISPLAY_SWAP_PRUNE_ON_CLEANUP", "IMAGE_SWAP_PRUNE_ON_CLEANUP"),
        description="Run swap prune during scheduler temp cleanup cycles.",
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
    public_mdns_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_MDNS_HOST", "API_PUBLIC_MDNS_HOST"),
        description="Optional mDNS-resolvable hostname such as mimir.local for client bootstrap.",
    )
    public_port: int | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_PORT", "API_PUBLIC_PORT", "EXTERNAL_PORT"),
    )
    internal_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INTERNAL_BASE_URL", "CHANNEL_REQUEST_BASE_URL"),
        description=(
            "Base URL the API uses to call itself (e.g. channel /request-image). "
            "Defaults to http://127.0.0.1:<api_port>. Never use the public URL here: "
            "hairpinning through the LAN address fails from inside containers."
        ),
    )

    @property
    def internal_api_base_url(self) -> str:
        """Base URL for API self-calls (loopback by default)."""
        if self.internal_base_url:
            return self.internal_base_url.rstrip("/")
        return f"http://127.0.0.1:{self.api_port}"

    # --- Security / CORS ---
    secret_key: str = Field("change-me", validation_alias=AliasChoices("SECRET_KEY","JWT_SECRET","APP_SECRET"))
    # Raw CORS env value (string) to avoid early pydantic JSON coercion issues
    cors_origins_raw: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CORS_ORIGINS", "CORS_ALLOW_ORIGINS"),
        description="Raw CORS origins environment value (JSON array or comma-separated).",
    )
    # Extra origins appended to cors_origins without replacing the base list.
    # Useful for LAN/remote deployments: set CORS_ORIGINS_EXTRA=http://192.168.1.50:8080
    cors_origins_extra_raw: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CORS_ORIGINS_EXTRA"),
        description="Additional CORS origins to append (comma-separated or JSON array).",
    )
    # Final parsed list (intentionally given a dummy alias so env var CORS_ORIGINS maps ONLY to cors_origins_raw)
    # Without this, pydantic_settings will also try to feed the raw env value into this list field
    # (because the field name uppercases to CORS_ORIGINS) and attempt JSON decoding before our model validator runs.
    cors_origins: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("_CORS_ORIGINS_DERIVED_DO_NOT_SET"),
    )

    @field_validator("cors_origins_raw", mode="before")
    @classmethod
    def _normalize_cors_raw(cls, v):
        # Accept empty string as None; leave other values untouched for later parsing
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @model_validator(mode="after")
    def _finalize_cors(self):
        """Populate `cors_origins` from `cors_origins_raw` + `cors_origins_extra_raw`.

        Both fields accept either a JSON array (e.g. '["https://a","https://b"]') or a
        comma-separated list (e.g. 'https://a, https://b'). Whitespace and empty
        segments are stripped. Malformed JSON falls back to comma parsing.

        CORS_ORIGINS_EXTRA appends to the base list without replacing it, making it
        easy to add LAN/remote origins (e.g. http://192.168.1.50:8080) without
        having to duplicate the full default list.
        """
        def _parse(raw: str | None) -> list[str]:
            if not raw:
                return []
            s = raw.strip()
            if s.startswith("["):
                import json
                try:
                    loaded = json.loads(s)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(loaded, list):
                        return [str(item).strip() for item in loaded if str(item).strip()]
            return [part.strip() for part in s.split(",") if part.strip()]

        self.cors_origins = _parse(self.cors_origins_raw) + _parse(self.cors_origins_extra_raw)
        return self

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
    mdns_external_feed_enabled: bool = Field(
        False,
        validation_alias=AliasChoices("MDNS_EXTERNAL_FEED_ENABLED",),
        description="Accept mDNS discovery events from an external host-network discovery service.",
    )
    mdns_external_feed_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MDNS_EXTERNAL_FEED_TOKEN", "MIMIR_DISCOVERY_TOKEN"),
        description="Optional shared secret required for external mDNS ingest requests.",
    )
    mdns_update_interval: int = Field(30, validation_alias=AliasChoices("MDNS_UPDATE_INTERVAL",))  # seconds
    mdns_offline_timeout: int = Field(120, validation_alias=AliasChoices("MDNS_OFFLINE_TIMEOUT",))  # seconds

    # --- MQTT Presence (for instant online/offline detection) ---
    mqtt_enabled: bool = Field(True, validation_alias=AliasChoices("MQTT_ENABLED",))
    mqtt_broker_host: str = Field("localhost", validation_alias=AliasChoices("MQTT_BROKER_HOST", "MQTT_HOST"))
    mqtt_broker_port: int = Field(1883, validation_alias=AliasChoices("MQTT_BROKER_PORT", "MQTT_PORT"))
    mqtt_public_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MQTT_PUBLIC_HOST", "MQTT_ADVERTISED_HOST"),
        description="Optional externally reachable hostname for clients.",
    )
    mqtt_public_port: int | None = Field(
        default=None,
        validation_alias=AliasChoices("MQTT_PUBLIC_PORT", "MQTT_ADVERTISED_PORT"),
        description="Optional externally reachable port for clients.",
    )
    mqtt_username: str | None = Field(default=None, validation_alias=AliasChoices("MQTT_USERNAME", "MQTT_USER"))
    mqtt_password: str | None = Field(default=None, validation_alias=AliasChoices("MQTT_PASSWORD", "MQTT_PASS"))
    mqtt_expose_credentials: bool = Field(
        False,
        validation_alias=AliasChoices("MQTT_EXPOSE_CREDENTIALS",),
        description="If true, expose MQTT username/password in the client config endpoint.",
    )
    mqtt_client_id_prefix: str = Field("mimir", validation_alias=AliasChoices("MQTT_CLIENT_ID_PREFIX",))

    @field_validator(
        "public_host",
        "public_mdns_host",
        "public_port",
        "mqtt_public_host",
        "mqtt_public_port",
        "mqtt_username",
        "mqtt_password",
        mode="before",
    )
    @classmethod
    def _blank_env_to_none(cls, value):
        """Treat blank env values as unset.

        Env templates ship optional vars as e.g. ``MQTT_PUBLIC_PORT=`` and
        docker compose passes the empty string through; without this,
        ``int | None`` fields fail validation on ``""``.
        """
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @staticmethod
    def _normalize_optional_host(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _is_loopback_host(candidate: str | None) -> bool:
        if not candidate:
            return True
        normalized = candidate.strip().strip("[]").lower()
        return normalized in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    @staticmethod
    def _looks_internal_container_host(candidate: str | None) -> bool:
        if not candidate:
            return False
        normalized = candidate.strip().lower()
        base_host = normalized[:-6] if normalized.endswith(".local") else normalized
        if re.fullmatch(r"[0-9a-f]{12,64}", base_host):
            return True
        if "." in normalized and not normalized.endswith(".local"):
            return False
        internal_names = {
            "api",
            "db",
            "mqtt",
            "redis",
            "web",
            "discovery",
            "mimir-api",
            "mimir-db",
            "mimir-mqtt",
            "mimir-redis",
            "mimir-web",
            "mimir-discovery",
        }
        return normalized in internal_names or base_host in internal_names

    @classmethod
    def _is_client_reachable_host(cls, candidate: str | None) -> bool:
        normalized = cls._normalize_optional_host(candidate)
        if not normalized:
            return False
        if cls._is_loopback_host(normalized) or cls._looks_internal_container_host(normalized):
            return False
        return True

    @staticmethod
    def _discover_primary_ipv4() -> str | None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except OSError:
            return None

    @field_validator("public_host", "public_mdns_host", "mqtt_public_host", mode="before")
    @classmethod
    def _normalize_optional_hosts(cls, value):
        return cls._normalize_optional_host(value)

    # --- MQTT Discovery (hybrid Redis) ---
    mqtt_discovery_enabled: bool = Field(
        True,
        validation_alias=AliasChoices("MQTT_DISCOVERY_ENABLED",),
        description="Enable heartbeat-based MQTT discovery for non-mDNS displays.",
    )
    mqtt_discovery_expiry_seconds: int = Field(
        600,
        validation_alias=AliasChoices("MQTT_DISCOVERY_EXPIRY_SECONDS",),
        description="Seconds before a DISCOVERED device without capabilities expires.",
    )
    mqtt_discovery_preregistered_expiry_seconds: int = Field(
        86400,
        validation_alias=AliasChoices("MQTT_DISCOVERY_PREREGISTERED_EXPIRY_SECONDS",),
        description="Seconds before a PRE_REGISTERED (not approved) device expires.",
    )
    mqtt_discovery_offline_grace_seconds: int = Field(
        120,
        validation_alias=AliasChoices("MQTT_DISCOVERY_OFFLINE_GRACE_SECONDS",),
        description="Heartbeat silence interval to mark device OFFLINE.",
    )
    mqtt_discovery_ws_debounce_seconds: float = Field(
        1.5,
        validation_alias=AliasChoices("MQTT_DISCOVERY_WS_DEBOUNCE_SECONDS",),
        description="Minimum seconds between websocket broadcast updates per device.",
    )

    # --- Push / Scene Refresh Tunables ---
    push_debounce_seconds: float = Field(
        5.0,
        validation_alias=AliasChoices("PUSH_DEBOUNCE_SECONDS", "CHANNEL_PUSH_DEBOUNCE_SECONDS"),
        description="Minimum seconds between successive refreshes of the same scene triggered by push events.",
    )
    push_channel_scene_cache_ttl: float = Field(
        30.0,
        validation_alias=AliasChoices("PUSH_CHANNEL_SCENE_CACHE_TTL", "CHANNEL_SCENE_CACHE_TTL_SECONDS"),
        description="TTL (seconds) for channel->scene mapping cache in push consumer.",
    )
    push_fallback_stale_check_interval: float = Field(
        60.0,
        validation_alias=AliasChoices("PUSH_FALLBACK_STALE_CHECK_INTERVAL", "PUSH_STALE_CHECK_INTERVAL_SECONDS"),
        description="Interval (seconds) for background task that triggers fallback refreshes when push scenes go stale.",
    )

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
        2. Explicit public_mdns_host (for example: mimir.local)
        3. Primary outbound IPv4 (UDP connect probe)
        4. hostname + ".local" (for mDNS-capable environments)
        5. Local system hostname (socket.gethostname())
        6. Fallback 127.0.0.1 (last resort)

        The bare hostname ranks below its .local form because clients on other
        machines usually cannot resolve it (only the server itself can), while
        mDNS resolves hostname.local across the LAN.

        Ports: omit when standard (80 http / 443 https). This avoids confusing some
        embedded HTTP clients that mishandle explicit default ports.
        """
        scheme = self.public_scheme or "http"

        # Candidate hostnames in priority order (deduplicated later)
        hostname = socket.gethostname()
        candidates: list[str | None] = [
            self.public_host,
            self.public_mdns_host,
            self._discover_primary_ipv4(),
            f"{hostname}.local",
            hostname,
        ]

        seen = set()
        chosen_host: str | None = None
        for cand in candidates:
            if not cand or cand in seen:
                continue
            seen.add(cand)
            if self._is_client_reachable_host(cand):
                chosen_host = cand
                break

        if chosen_host is None:
            chosen_host = "127.0.0.1"

        port = self.public_port if self.public_port is not None else self.api_port
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            return f"{scheme}://{chosen_host}"
        return f"{scheme}://{chosen_host}:{port}"

settings = Settings()
