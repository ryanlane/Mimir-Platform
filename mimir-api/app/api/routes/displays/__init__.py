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

"""Display Client API Routes.

Provides endpoints to query and manage display clients (registered & discovered).

Sub-modules:
- discovery   — mDNS ingest, discovery status/live/start/stop, MQTT config
- provisioning — provision bundle, provision-from-setup, bootstrap, provision-register
- pairing     — short-code pairing (pair/claim)
- crud        — list, get, update, delete, status
- scenes      — scene assignment / unassignment
- images      — last-image and image history endpoints
"""
from fastapi import APIRouter

from .crud import router as crud_router
from .discovery import router as discovery_router
from .images import router as images_router
from .pairing import router as pairing_router
from .provisioning import router as provisioning_router
from .scenes import router as scenes_router
from .virtual import router as virtual_router

router = APIRouter(prefix="/displays", tags=["displays"])

# Discovery routes first — they have specific paths (e.g. /mdns/ingest, /discovery/*)
# that must be registered before the wildcard /{display_id} routes in crud.
router.include_router(discovery_router)
router.include_router(provisioning_router)
router.include_router(pairing_router)
router.include_router(images_router)
router.include_router(scenes_router)
# Virtual display routes before crud so /virtual/presets and /virtual/{id}
# don't get swallowed by the /{display_id} wildcard.
router.include_router(virtual_router)
router.include_router(crud_router)
