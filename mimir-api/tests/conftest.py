"""
Test Configuration and Base Fixtures
Provides common test setup, database fixtures, and utilities
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.displays._helpers import get_db as displays_get_db
from app.db.models import Base, DisplayClient, Scene
from app.db.session import get_session
from app.main import create_app


@pytest.fixture(scope="session")
def test_db_engine():
    """In-memory SQLite engine shared across the test session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def test_db_session(test_db_engine):
    """Fresh database session per test; tables are emptied afterwards."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = TestingSessionLocal()
    try:
        yield session
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def app(test_db_session):
    """FastAPI app wired to the test database via dependency override."""
    application = create_app()

    def override_get_session():
        yield test_db_session

    application.dependency_overrides[get_session] = override_get_session
    application.dependency_overrides[displays_get_db] = override_get_session
    return application


@pytest.fixture()
def client(app):
    """Test client.

    Deliberately NOT used as a context manager: entering the client would run
    the app lifespan, which starts the scheduler, MQTT, and mDNS discovery.
    Routes work without it.
    """
    return TestClient(app)


@pytest.fixture()
def sample_scene_payload():
    """Scene payload in the wire format the scenes API accepts."""
    return {
        "id": "test-scene",
        "name": "Test Scene",
        "channels": [{"channel_id": "test-channel", "config": {"background": "blue"}}],
        "distribution_mode": "MIRROR",
        "is_active": False,
    }


@pytest.fixture()
def seeded_display(test_db_session):
    """A registered display persisted directly through the ORM."""
    display = DisplayClient(
        id="seeded-display",
        name="Seeded Display",
        location="Test Lab",
        hostname="seeded-host",
        is_online=False,
    )
    test_db_session.add(display)
    test_db_session.commit()
    return display


@pytest.fixture()
def seeded_scene(test_db_session):
    """A scene persisted directly through the ORM."""
    scene = Scene(
        id="seeded-scene",
        name="Seeded Scene",
        channels=[{"channel_id": "test-channel"}],
        distribution_mode="MIRROR",
        is_active=False,
        update_strategy="scheduler",
    )
    test_db_session.add(scene)
    test_db_session.commit()
    return scene
