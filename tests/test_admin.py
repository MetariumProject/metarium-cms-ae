"""Unit tests for /api/admin/* endpoints."""
from unittest import mock

import pytest

from tests.conftest import ADMIN_ADDRESS, SCRIBE_ADDRESS


# ---------------------------------------------------------------------------
# POST /api/admin/scribes  (add scribe)
# ---------------------------------------------------------------------------

class TestAddScribe:

    def test_add_scribe_as_admin(self, client, mock_admin_user, admin_headers):
        """Admin adds a new scribe => 201."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.Keypair") as MockKP, \
             mock.patch("api.admin_routes.Scribe.is_scribe", return_value=False), \
             mock.patch("api.admin_routes.Scribe.create") as mock_create:
            MockKP.return_value = mock.MagicMock()

            resp = client.post("/api/admin/scribes", headers=admin_headers, json={
                "address": SCRIBE_ADDRESS,
            })
            assert resp.status_code == 201
            mock_create.assert_called_once()

    def test_add_scribe_as_non_admin(self, client, mock_scribe_user, scribe_headers):
        """Non-admin tries to add scribe => 403."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", return_value=False):
            resp = client.post("/api/admin/scribes", headers=scribe_headers, json={
                "address": "5SomeOtherAddress",
            })
            assert resp.status_code == 403

    def test_add_duplicate_scribe(self, client, mock_admin_user, admin_headers):
        """Address already a scribe => 409."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.Keypair") as MockKP, \
             mock.patch("api.admin_routes.Scribe.is_scribe", return_value=True):
            MockKP.return_value = mock.MagicMock()

            resp = client.post("/api/admin/scribes", headers=admin_headers, json={
                "address": SCRIBE_ADDRESS,
            })
            assert resp.status_code == 409

    def test_add_admin_as_scribe(self, client, mock_admin_user, admin_headers):
        """Cannot add admin address as scribe => 400."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", return_value=True), \
             mock.patch("api.admin_routes.Keypair") as MockKP:
            MockKP.return_value = mock.MagicMock()

            resp = client.post("/api/admin/scribes", headers=admin_headers, json={
                "address": ADMIN_ADDRESS,
            })
            assert resp.status_code == 400

    def test_add_invalid_ss58(self, client, mock_admin_user, admin_headers):
        """Invalid SS58 address => 400."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.Keypair", side_effect=Exception("bad")):
            resp = client.post("/api/admin/scribes", headers=admin_headers, json={
                "address": "INVALID",
            })
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/admin/scribes  (remove scribe)
# ---------------------------------------------------------------------------

class TestRemoveScribe:

    def test_remove_scribe(self, client, mock_admin_user, admin_headers):
        """Admin removes an existing scribe => 200."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.Scribe.delete_scribe", return_value=True):
            resp = client.delete("/api/admin/scribes", headers=admin_headers, json={
                "address": SCRIBE_ADDRESS,
            })
            assert resp.status_code == 200

    def test_remove_nonexistent(self, client, mock_admin_user, admin_headers):
        """Remove non-existent scribe => 404."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.Scribe.delete_scribe", return_value=False):
            resp = client.delete("/api/admin/scribes", headers=admin_headers, json={
                "address": "5NonExistent",
            })
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/admin/scribes  (list)
# ---------------------------------------------------------------------------

class TestListScribes:

    def test_list_scribes(self, client, mock_admin_user, admin_headers):
        """Admin lists scribes => 200."""
        mock_scribe = mock.MagicMock()
        mock_scribe.address = SCRIBE_ADDRESS
        mock_scribe.granted_by = ADMIN_ADDRESS
        mock_scribe.created_at = None

        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.Scribe.list_all", return_value=[mock_scribe]):
            resp = client.get("/api/admin/scribes", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["scribes"]) == 1


# ---------------------------------------------------------------------------
# GET /api/admin/config
# ---------------------------------------------------------------------------

class TestGetConfig:

    def test_get_config(self, client, mock_admin_user, admin_headers):
        """Admin gets config => 200."""
        mock_config = mock.MagicMock()
        mock_config.admin_address = ADMIN_ADDRESS
        mock_config.created_at = None

        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.CMSConfig.get_config", return_value=mock_config):
            resp = client.get("/api/admin/config", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.get_json()["admin_address"] == ADMIN_ADDRESS

    def test_get_config_not_set(self, client, mock_admin_user, admin_headers):
        """Config not yet created => 404."""
        with mock.patch("api.admin_routes.CMSConfig.is_admin", side_effect=lambda a: a == ADMIN_ADDRESS), \
             mock.patch("api.admin_routes.CMSConfig.get_config", return_value=None):
            resp = client.get("/api/admin/config", headers=admin_headers)
            assert resp.status_code == 404
