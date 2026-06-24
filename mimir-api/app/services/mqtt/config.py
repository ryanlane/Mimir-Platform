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

# app/services/mqtt/config.py
from app.config import settings


def host() -> str: return getattr(settings, "mqtt_broker_host", "localhost")
def port() -> int: return int(getattr(settings, "mqtt_broker_port", 1883))
def enabled() -> bool: return bool(getattr(settings, "mqtt_enabled", True))
