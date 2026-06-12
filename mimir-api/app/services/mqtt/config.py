# app/services/mqtt/config.py
from app.config import settings


def host() -> str: return getattr(settings, "mqtt_broker_host", "localhost")
def port() -> int: return int(getattr(settings, "mqtt_broker_port", 1883))
def enabled() -> bool: return bool(getattr(settings, "mqtt_enabled", True))
