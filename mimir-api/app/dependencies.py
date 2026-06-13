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
