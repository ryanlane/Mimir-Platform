"""Unit tests for MQTT presence → display_clients.is_online DB sync.

Covers the /screens staleness bug: a registered MQTT display must be marked
offline in the DB when its status topic reports offline (graceful publish or
broker LWT), and online again when it returns. Without the sync, the row
keeps is_online=True forever after the client exits.
"""
import pytest

from app.db.models import DisplayClient
from app.services.mqtt.presence import MqttPresenceService


@pytest.fixture()
def presence_service():
    return MqttPresenceService()


@pytest.fixture()
def patched_sessionlocal(test_db_engine, test_db_session, monkeypatch):
    """Point the service's lazily-imported SessionLocal at the test DB."""
    from sqlalchemy.orm import sessionmaker

    testing_sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    monkeypatch.setattr("app.db.base.SessionLocal", testing_sessionmaker)
    return testing_sessionmaker


def _make_display(session, hostname: str, *, is_online: bool) -> DisplayClient:
    display = DisplayClient(
        id=f"id-{hostname}",
        name=f"Display {hostname}",
        hostname=hostname,
        display_type="registered",
        discovery_method="mqtt_registration",
        is_online=is_online,
    )
    session.add(display)
    session.commit()
    return display


@pytest.mark.unit
class TestOnlineStateSync:
    async def test_offline_status_marks_db_row_offline(
        self, presence_service, test_db_session, patched_sessionlocal
    ):
        _make_display(test_db_session, "win-asgard", is_online=True)

        # Device was never seen "online" by this service instance — the
        # server-restart case where the retained LWT replays first. The DB
        # write must happen regardless of the in-memory guards.
        await presence_service._handle_status_message("win-asgard", {"status": "offline"})

        test_db_session.expire_all()
        row = test_db_session.query(DisplayClient).filter_by(hostname="win-asgard").one()
        assert row.is_online is False
        assert row.last_seen is not None

    async def test_online_status_marks_db_row_online(
        self, presence_service, test_db_session, patched_sessionlocal
    ):
        _make_display(test_db_session, "win-asgard", is_online=False)

        await presence_service._handle_status_message("win-asgard", {"status": "online"})

        test_db_session.expire_all()
        row = test_db_session.query(DisplayClient).filter_by(hostname="win-asgard").one()
        assert row.is_online is True

    async def test_offline_then_online_round_trip(
        self, presence_service, test_db_session, patched_sessionlocal
    ):
        _make_display(test_db_session, "win-asgard", is_online=True)

        await presence_service._handle_status_message("win-asgard", {"status": "offline"})
        await presence_service._handle_status_message("win-asgard", {"status": "online"})

        test_db_session.expire_all()
        row = test_db_session.query(DisplayClient).filter_by(hostname="win-asgard").one()
        assert row.is_online is True

    async def test_unknown_device_is_ignored(
        self, presence_service, test_db_session, patched_sessionlocal
    ):
        # No row for this hostname — must not raise, must not create rows.
        await presence_service._handle_status_message("ghost-host", {"status": "offline"})

        assert test_db_session.query(DisplayClient).count() == 0

    async def test_non_lifecycle_status_does_not_touch_db(
        self, presence_service, test_db_session, patched_sessionlocal, monkeypatch
    ):
        _make_display(test_db_session, "win-asgard", is_online=True)

        called = False

        async def _spy(*args, **kwargs):
            nonlocal called
            called = True

        monkeypatch.setattr(presence_service, "_sync_display_online_state", _spy)
        await presence_service._handle_status_message("win-asgard", {"status": "unknown"})

        assert called is False
