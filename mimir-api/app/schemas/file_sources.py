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
File Source schemas — user-configured media roots (local mounts, SMB shares)
browsable from the web UI and shared across file-consuming channel plugins.
"""
from typing import Any, Literal

from pydantic import BaseModel


class FileSourceBase(BaseModel):
    """Base file source schema"""
    name: str
    type: Literal["local", "smb"]
    config: dict[str, Any] = {}
    enabled: bool = True


class FileSourceCreate(FileSourceBase):
    """Schema for creating file sources"""
    id: str | None = None


class FileSourceUpdate(BaseModel):
    """Schema for updating file sources (partial)"""
    name: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class FileSourceResponse(FileSourceBase):
    """File source as returned by the API.

    ``config`` is redacted: SMB passwords are replaced with a boolean
    ``has_password`` marker so credentials never round-trip to the browser.
    """
    id: str

    class Config:
        from_attributes = True


class FileSourceListResponse(BaseModel):
    sources: list[FileSourceResponse]
    total: int


class BrowseEntry(BaseModel):
    """One directory entry in a browse listing"""
    name: str
    path: str            # path relative to the source root
    is_dir: bool
    size: int = 0


class BrowseResponse(BaseModel):
    source_id: str
    path: str                       # relative path browsed ('' = source root)
    breadcrumbs: list[dict[str, str]]  # [{name, path}] from root to current
    entries: list[BrowseEntry]


class SourceTestResult(BaseModel):
    ok: bool
    message: str
