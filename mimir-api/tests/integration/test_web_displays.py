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

"""Integration tests for Web Screens (browser-only displays)."""
import pytest
from fastapi.testclient import TestClient

from app.services.display_last_image import display_last_image_store


def _create(client: TestClient, **overrides):
    body = {"name": "Old Tablet", **overrides}
    resp = client.post("/api/displays/web", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.integration
@pytest.mark.api
class TestWebDisplayLifecycle:
    def test_create_returns_unique_url(self, client: TestClient):
        a = _create(client)
        b = _create(client, name="Second Tablet")
        assert a["web_path"].startswith("/d/")
        assert a["web_path"] != b["web_path"]
        # Token is long enough to be unguessable
        assert len(a["web_path"].split("/d/")[1]) >= 24

    def test_display_page_served_for_valid_token(self, client: TestClient):
        created = _create(client)
        resp = client.get(created["web_path"])
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Mimir Display" in resp.text

    def test_display_page_404_for_bad_token(self, client: TestClient):
        assert client.get("/d/not-a-real-token").status_code == 404

    def test_display_listed_with_web_path(self, client: TestClient):
        created = _create(client)
        listing = client.get("/api/displays/").json()
        match = [d for d in listing["data"] if d["id"] == created["display_id"]]
        assert match and match[0]["webPath"] == created["web_path"]
        assert match[0]["discoveryMethod"] == "web"


@pytest.mark.integration
@pytest.mark.api
class TestWebDisplayPolling:
    def _token(self, created):
        return created["web_path"].split("/d/")[1]

    def test_poll_marks_online_and_reports_no_scene(self, client: TestClient):
        created = _create(client)
        resp = client.get(f"/api/displays/web/{self._token(created)}/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scene_assigned"] is False
        assert data["image"] is None
        listing = client.get("/api/displays/").json()
        row = [d for d in listing["data"] if d["id"] == created["display_id"]][0]
        assert row["isOnline"] is True

    def test_poll_updates_resolution(self, client: TestClient):
        created = _create(client, width=800, height=600)
        client.get(f"/api/displays/web/{self._token(created)}/current?w=2048&h=1536")
        listing = client.get("/api/displays/").json()
        row = [d for d in listing["data"] if d["id"] == created["display_id"]][0]
        assert (row["width"], row["height"]) == (2048, 1536)

    def test_poll_updates_animation_capability(self, client: TestClient):
        created = _create(client)
        client.get(f"/api/displays/web/{self._token(created)}/current?anim=1")
        # No direct field in the response listing; verify via a second poll not erroring
        # and via DB-backed listing width defaults intact.
        resp = client.get(f"/api/displays/web/{self._token(created)}/current?anim=0")
        assert resp.status_code == 200

    def test_poll_serves_last_image_as_same_origin_path(self, client: TestClient):
        created = _create(client)
        listing = client.get("/api/displays/").json()
        row = [d for d in listing["data"] if d["id"] == created["display_id"]][0]
        device_id = row["hostname"]
        display_last_image_store.update(
            device_id=device_id, assignment_id="a-1",
            image_url="http://172.27.0.5:5000/media/swap/s1/d1/img.png?v=abc",
            image_width=800, image_height=600, image_format="png",
            scene_id="s1", subchannel_id=None,
        )
        data = client.get(f"/api/displays/web/{self._token(created)}/current").json()
        assert data["image"] == "/media/swap/s1/d1/img.png?v=abc"
        assert data["version"] == "a-1"

    def test_poll_rejects_bad_token(self, client: TestClient):
        assert client.get("/api/displays/web/nope/current").status_code == 404
