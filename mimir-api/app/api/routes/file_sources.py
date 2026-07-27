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

"""
File Sources API Routes

CRUD for operator-configured media roots plus the browse endpoint that backs
the shared file-explorer picker used across channel plugins.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import FileSource
from app.schemas.file_sources import (
    BrowseEntry,
    BrowseResponse,
    FileSourceCreate,
    FileSourceListResponse,
    FileSourceResponse,
    FileSourceUpdate,
    SourceTestResult,
)
from app.services import file_sources as svc

router = APIRouter(prefix="/sources", tags=["file-sources"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _to_response(source: FileSource) -> FileSourceResponse:
    return FileSourceResponse(
        id=source.id,
        name=source.name,
        type=source.type,
        config=svc.redact_config(source.type, source.config),
        enabled=source.enabled,
    )


def _get_or_404(db: Session, source_id: str) -> FileSource:
    source = db.query(FileSource).filter(FileSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="File source not found")
    return source


@router.get("", response_model=FileSourceListResponse)
async def list_sources(db: Session = Depends(get_db)):
    sources = db.query(FileSource).order_by(FileSource.created_at).all()
    return FileSourceListResponse(
        sources=[_to_response(s) for s in sources], total=len(sources))


@router.post("", response_model=FileSourceResponse)
async def create_source(data: FileSourceCreate, db: Session = Depends(get_db)):
    source = FileSource(
        id=data.id or str(uuid.uuid4()),
        name=data.name,
        type=data.type,
        config=data.config,
        enabled=data.enabled,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_response(source)


@router.get("/{source_id}", response_model=FileSourceResponse)
async def get_source(source_id: str, db: Session = Depends(get_db)):
    return _to_response(_get_or_404(db, source_id))


@router.put("/{source_id}", response_model=FileSourceResponse)
async def update_source(source_id: str, data: FileSourceUpdate,
                        db: Session = Depends(get_db)):
    source = _get_or_404(db, source_id)
    updates = data.model_dump(exclude_unset=True)
    if "config" in updates:
        # Preserve the stored SMB password when the client omits it — the
        # redacted config the UI round-trips never contains the secret.
        new_cfg = dict(updates["config"] or {})
        new_cfg.pop("has_password", None)
        if source.type == "smb" and not new_cfg.get("password"):
            existing = (source.config or {}).get("password")
            if existing:
                new_cfg["password"] = existing
        updates["config"] = new_cfg
    for key, value in updates.items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return _to_response(source)


@router.delete("/{source_id}")
async def delete_source(source_id: str, db: Session = Depends(get_db)):
    source = _get_or_404(db, source_id)
    db.delete(source)
    db.commit()
    return {"message": "File source deleted successfully"}


@router.post("/{source_id}/test", response_model=SourceTestResult)
async def test_source(source_id: str, db: Session = Depends(get_db)):
    source = _get_or_404(db, source_id)
    ok, message = svc.test_source(source)
    return SourceTestResult(ok=ok, message=message)


@router.get("/{source_id}/resolve")
async def resolve_source_path(
    source_id: str,
    path: str = Query(..., description="Relative path within the source"),
    db: Session = Depends(get_db),
):
    """Turn a source-relative path into a real local filesystem path.

    Local sources resolve in place; SMB files are copied into a server-side
    cache on first use. Callers must run in the same filesystem namespace as
    the API (e.g. an embedded channel plugin) — the returned path is only
    meaningful there, never to a browser.
    """
    source = _get_or_404(db, source_id)
    if not source.enabled:
        raise HTTPException(status_code=400, detail="File source is disabled")
    try:
        local_path = svc.localize(source, path)
    except svc.FileSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"local_path": str(local_path)}


@router.get("/{source_id}/browse", response_model=BrowseResponse)
async def browse_source(
    source_id: str,
    path: str = Query("", description="Relative path within the source"),
    extensions: str = Query("", description="Comma-separated file extensions to include (e.g. mp4,mkv)"),
    db: Session = Depends(get_db),
):
    source = _get_or_404(db, source_id)
    if not source.enabled:
        raise HTTPException(status_code=400, detail="File source is disabled")
    ext_list = [e.strip() for e in extensions.split(",") if e.strip()] or None
    try:
        listing = svc.browse(source, path, ext_list)
    except svc.FileSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BrowseResponse(
        source_id=source.id,
        path=listing.path,
        breadcrumbs=listing.breadcrumbs,
        entries=[BrowseEntry(name=e.name, path=e.path, is_dir=e.is_dir, size=e.size)
                 for e in listing.entries],
    )
