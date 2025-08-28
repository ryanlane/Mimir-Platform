"""
Database base configuration for Mimir API
Contains the SQLAlchemy engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Decide engine kwargs based on backend
url = make_url(settings.database_url)
engine_kwargs = {
    "echo": False,  # Disable SQL query logging for cleaner logs
    "future": True,  # 2.x style
}

if url.get_backend_name() == "sqlite":
    # SQLite: don't pass pool sizing; allow cross-thread use of the file DB
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False},
        "pool_pre_ping": settings.database_pool_pre_ping,
    })
else:
    # Client/server DBs (Postgres/MySQL/etc.): apply pool tuning
    engine_kwargs.update({
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "pool_recycle": settings.database_pool_recycle,
        "pool_pre_ping": settings.database_pool_pre_ping,
    })

# Create engine
engine = create_engine(settings.database_url, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Import models' Base (your project defines it there)
from app.db.models import Base  # noqa: E402
