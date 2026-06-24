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
Dependency injection for Mimir API
Provides FastAPI dependencies for request-scoped services
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_session


def get_scene_service(db: Session = Depends(get_session)):
    """Get scene service instance with database dependency"""
    from app.services.scene_service import SceneService
    return SceneService(db)
