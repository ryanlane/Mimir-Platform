"""Unit tests for MqttSceneAssignmentService.send_display_image.

Covers the optional `metadata` field (title/artist/etc, forwarded from a
channel's X-Artwork-Metadata response header — see scene_refresh_service's
_decode_metadata_header) that capable display clients render as an overlay.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.mqtt.publisher import MqttSceneAssignmentService


@pytest.fixture()
def service():
    svc = MqttSceneAssignmentService.__new__(MqttSceneAssignmentService)
    svc.publish_command = AsyncMock(return_value=True)  # type: ignore[method-assign]
    return svc


@pytest.mark.unit
class TestSendDisplayImageMetadata:
    async def test_metadata_included_when_provided(self, service):
        metadata = {"title": "Wheat Field with Cypresses", "artist": "van Gogh"}

        await service.send_display_image(
            device_id="disp-a",
            image_url="http://mimir.local:5000/swap/img.jpg",
            metadata=metadata,
        )

        payload = service.publish_command.await_args.args[1]
        assert payload["metadata"] == metadata

    async def test_metadata_key_omitted_when_none(self, service):
        await service.send_display_image(
            device_id="disp-a",
            image_url="http://mimir.local:5000/swap/img.jpg",
        )

        payload = service.publish_command.await_args.args[1]
        assert "metadata" not in payload

    async def test_metadata_key_omitted_when_empty_dict(self, service):
        await service.send_display_image(
            device_id="disp-a",
            image_url="http://mimir.local:5000/swap/img.jpg",
            metadata={},
        )

        payload = service.publish_command.await_args.args[1]
        assert "metadata" not in payload

    async def test_other_fields_unaffected_by_metadata(self, service):
        await service.send_display_image(
            device_id="disp-a",
            image_url="http://mimir.local:5000/swap/img.jpg",
            assignment_id="asn-1",
            metadata={"title": "Test"},
        )

        payload = service.publish_command.await_args.args[1]
        assert payload["type"] == "display_image"
        assert payload["image_url"] == "http://mimir.local:5000/swap/img.jpg"
        assert payload["assignment_id"] == "asn-1"
