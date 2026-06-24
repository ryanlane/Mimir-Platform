# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# app/services/mqtt/topics.py

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
