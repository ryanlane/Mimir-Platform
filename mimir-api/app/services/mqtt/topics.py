# app/services/mqtt/topics.py
from dataclasses import dataclass

PREFIX = "mimir"

def cmd_topic(target_id: str) -> str:
    return f"{PREFIX}/{target_id}/cmd"

def evt_topic_wildcard() -> str:
    return f"{PREFIX}/+/evt"

def status_topic_wildcard() -> str:
    return f"{PREFIX}/+/status"

def heartbeat_topic_wildcard() -> str:
    return f"{PREFIX}/+/heartbeat"

def api_status_topic(client_id: str) -> str:
    return f"{PREFIX}/api/{client_id}/status"

# Pairing topics
PAIR_REQUEST_TOPIC = f"{PREFIX}/registry/pair"       # device → server: pairing request with 6-char code
PAIR_ACK_TOPIC_FMT = f"{PREFIX}/{{device_id}}/pair/ack"  # server → device: acknowledgment

def pair_ack_topic(device_id: str) -> str:
    return f"{PREFIX}/{device_id}/pair/ack"
