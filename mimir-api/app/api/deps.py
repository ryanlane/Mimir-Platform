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
Common dependencies used across route handlers
"""
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import get_current_api_key
from app.db.session import get_session

logger = get_logger("app.deps")


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency
    Yields a SQLAlchemy session and ensures it's closed after use
    """
    db = next(get_session())
    try:
        yield db
    finally:
        db.close()


def get_optional_api_key(
    api_key: str | None = Depends(get_current_api_key)
) -> str | None:
    """
    Optional API key dependency
    Returns None if no API key provided
    """
    return api_key


def require_api_key(
    api_key: str | None = Depends(get_current_api_key)
) -> str:
    """
    Required API key dependency
    Raises HTTPException if no valid API key provided
    """
    if not api_key:
        logger.warning("API key required but not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required for this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return api_key


def get_current_user_id(
    api_key: str = Depends(require_api_key)
) -> str:
    """
    Get current user ID from API key
    TODO: Implement user lookup from API key
    """
    # For now, return a placeholder
    # In a real implementation, you would look up the user associated with the API key
    return "default_user"


class PaginationParams:
    """Pagination parameters for list endpoints"""

    def __init__(
        self,
        page: int = 1,
        size: int = 20,
        max_size: int = 100
    ):
        # Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page must be >= 1"
            )

        if size < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Size must be >= 1"
            )

        if size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Size must be <= {max_size}"
            )

        self.page = page
        self.size = size
        self.offset = (page - 1) * size
        self.limit = size


def get_pagination_params(
    page: int = 1,
    size: int = 20
) -> PaginationParams:
    """Dependency to get pagination parameters"""
    return PaginationParams(page=page, size=size)


def get_channels_directory() -> str:
    """Get the channels directory from configuration"""
    from app.config import settings
    return settings.channels_directory


def get_redis_manager():
    """
    Get Redis manager if available
    Returns None if Redis is not enabled/available
    """
    from app.config import settings

    if not settings.redis_enabled:
        return None

    try:
        from app.services.distribution import get_redis_client
        return get_redis_client()
    except ImportError:
        logger.warning("Redis requested but not available")
        return None


def validate_content_type(
    content_type: str,
    allowed_types: list = None
) -> str:
    """
    Validate content type
    """
    if allowed_types is None:
        allowed_types = [
            "application/json",
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp"
        ]

    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type {content_type} not allowed. Allowed types: {allowed_types}"
        )

    return content_type
