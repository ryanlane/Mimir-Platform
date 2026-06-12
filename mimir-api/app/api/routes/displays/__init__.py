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

from .discovery import router as discovery_router
from .provisioning import router as provisioning_router
from .pairing import router as pairing_router
from .crud import router as crud_router
from .scenes import router as scenes_router
from .images import router as images_router


router = APIRouter(prefix="/displays", tags=["displays"])

# Discovery routes first — they have specific paths (e.g. /mdns/ingest, /discovery/*)
# that must be registered before the wildcard /{display_id} routes in crud.
router.include_router(discovery_router)
router.include_router(provisioning_router)
router.include_router(pairing_router)
router.include_router(images_router)
router.include_router(scenes_router)
router.include_router(crud_router)
