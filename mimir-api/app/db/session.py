"""
Database session management for Mimir API
Provides session creation and dependency injection utilities
"""
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import SessionLocal

logger = get_logger("app.db.session")


def get_session() -> Generator[Session, None, None]:
    """
    Create a database session
    Yields a SQLAlchemy session and ensures it's properly closed
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Session:
    """
    Create a database session for direct use (not recommended for FastAPI)
    Use get_session() with Depends() for FastAPI route handlers
    """
    return SessionLocal()


class DatabaseManager:
    """Database management utilities"""

    @staticmethod
    def health_check() -> bool:
        """Check database connectivity"""
        try:
            session = SessionLocal()
            # Simple query to test connection
            session.execute("SELECT 1")
            session.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    @staticmethod
    def get_connection_info() -> dict:
        """Get database connection information"""
        from app.config import settings
        from app.db.base import engine

        return {
            "database_url": settings.database_url,
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
            "is_sqlite": "sqlite" in settings.database_url,
            "engine_echo": engine.echo
        }
