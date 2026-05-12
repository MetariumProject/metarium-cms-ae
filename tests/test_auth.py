"""Unit tests for /api/auth/* endpoints."""
import json
from unittest import mock

import pytest

from tests.conftest import ADMIN_ADDRESS, SCRIBE_ADDRESS


# ---------------------------------------------------------------------------
# POST /api/auth/challenge
# ---------------------------------------------------------------------------

class TestChallenge:

    def test_challenge_valid_admin(self, client, admin_headers):
        """Valid admin address => 200 with challenge data."""
        with mock.patch("api.auth_routes.Keypair") as MockKP, \
             mock.patch("api.auth_routes.CMSConfig.is_admin", return_value=True), \
             mock.patch("api.auth_routes.Scribe.is_scribe", return_value=False), \
             mock.patch("api.auth_routes.Challenge.store_challenge"):
            # Keypair constructor should succeed (no exception)
            MockKP.return_value = mock.MagicMock()

            resp = client.post("/api/auth/challenge",
                               json={"address": ADMIN_ADDRESS})
            assert resp.status_code == 200
            data = resp.get_json()
            assert "challenge" in data

    def test_challenge_invalid_ss58(self, client):
        """Invalid SS58 address => 400."""
        with mock.patch("api.auth_routes.Keypair", side_effect=Exception("bad address")):
            resp = client.post("/api/auth/challenge",
                               json={"address": "INVALID"})
            assert resp.status_code == 400
            assert "Invalid SS58" in resp.get_json()["error"]

    def test_challenge_unauthorized(self, client):
        """Address that is neither admin nor scribe => 403."""
        with mock.patch("api.auth_routes.Keypair") as MockKP, \
             mock.patch("api.auth_routes.CMSConfig.is_admin", return_value=False), \
             mock.patch("api.auth_routes.Scribe.is_scribe", return_value=False):
            MockKP.return_value = mock.MagicMock()

            resp = client.post("/api/auth/challenge",
                               json={"address": ADMIN_ADDRESS})
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/auth/verify
# ---------------------------------------------------------------------------

class TestVerify:

    def test_verify_happy(self, client):
        """Correct signature => 200 with tokens & role."""
        challenge_data = {
            "address": ADMIN_ADDRESS,
            "timestamp": 1234567890,
            "nonce": "test-nonce",
            "message": "Sign this message to authenticate with Metarium CMS",
        }
        challenge_json_bytes = json.dumps(challenge_data, separators=(",", ":")).encode()
        message_hex = challenge_json_bytes.hex()
        signature_hex = "ab" * 64

        mock_challenge = mock.MagicMock()
        mock_challenge.challenge_data = challenge_data

        mock_user = mock.MagicMock()
        mock_user.address = ADMIN_ADDRESS
        mock_user.generate_tokens.return_value = {
            "access_token": "tok123",
            "access_token_expires": 9999999999.0,
            "refresh_token": "ref456",
            "refresh_token_expires": 9999999999.0,
        }

        with mock.patch("api.auth_routes.Keypair") as MockKP, \
             mock.patch("api.auth_routes.Challenge.get_challenge", return_value=mock_challenge), \
             mock.patch("api.auth_routes.Challenge.clear_challenge"), \
             mock.patch("api.auth_routes.User.create_or_update", return_value=mock_user), \
             mock.patch("api.auth_routes.CMSConfig.is_admin", return_value=True), \
             mock.patch("api.auth_routes.Scribe.is_scribe", return_value=False):
            MockKP.return_value.verify = mock.MagicMock()  # no exception = success

            resp = client.post("/api/auth/verify", json={
                "address": ADMIN_ADDRESS,
                "message": message_hex,
                "signature": signature_hex,
            })

            assert resp.status_code == 200
            data = resp.get_json()
            assert data["access_token"] == "tok123"
            assert data["refresh_token"] == "ref456"
            assert data["role"] == "admin"

    def test_verify_bad_signature(self, client):
        """Invalid signature => 401."""
        challenge_data = {"address": ADMIN_ADDRESS, "timestamp": 0, "nonce": "n", "message": "m"}
        challenge_json_bytes = json.dumps(challenge_data, separators=(",", ":")).encode()

        mock_challenge = mock.MagicMock()
        mock_challenge.challenge_data = challenge_data

        with mock.patch("api.auth_routes.Keypair") as MockKP, \
             mock.patch("api.auth_routes.Challenge.get_challenge", return_value=mock_challenge):
            MockKP.return_value.verify.side_effect = Exception("bad sig")

            resp = client.post("/api/auth/verify", json={
                "address": ADMIN_ADDRESS,
                "message": challenge_json_bytes.hex(),
                "signature": "ab" * 64,
            })
            assert resp.status_code == 401

    def test_verify_no_challenge(self, client):
        """No stored challenge => 400."""
        with mock.patch("api.auth_routes.Challenge.get_challenge", return_value=None):
            resp = client.post("/api/auth/verify", json={
                "address": ADMIN_ADDRESS,
                "message": "aa",
                "signature": "bb",
            })
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------

class TestRefresh:

    def test_refresh_happy(self, client):
        """Valid refresh token + still authorized => 200."""
        mock_user = mock.MagicMock()
        mock_user.address = ADMIN_ADDRESS
        mock_user.generate_tokens.return_value = {
            "access_token": "newtok",
            "access_token_expires": 9999999999.0,
            "refresh_token": "newref",
            "refresh_token_expires": 9999999999.0,
        }
        with mock.patch("api.auth_routes.User.get_by_refresh_token", return_value=mock_user), \
             mock.patch("api.auth_routes.CMSConfig.is_admin", return_value=True), \
             mock.patch("api.auth_routes.Scribe.is_scribe", return_value=False):

            resp = client.post("/api/auth/refresh",
                               json={"refresh_token": "oldref"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["access_token"] == "newtok"

    def test_refresh_revoked(self, client):
        """User whose ACL was removed => 403."""
        mock_user = mock.MagicMock()
        mock_user.address = ADMIN_ADDRESS
        with mock.patch("api.auth_routes.User.get_by_refresh_token", return_value=mock_user), \
             mock.patch("api.auth_routes.CMSConfig.is_admin", return_value=False), \
             mock.patch("api.auth_routes.Scribe.is_scribe", return_value=False):

            resp = client.post("/api/auth/refresh",
                               json={"refresh_token": "oldref"})
            assert resp.status_code == 403

    def test_refresh_invalid_token(self, client):
        """Unknown refresh token => 401."""
        with mock.patch("api.auth_routes.User.get_by_refresh_token", return_value=None):
            resp = client.post("/api/auth/refresh",
                               json={"refresh_token": "badtoken"})
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

class TestLogout:

    def test_logout(self, client, mock_admin_user, admin_headers):
        """Authenticated user logout => 200."""
        resp = client.post("/api/auth/logout", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Logged out"
        mock_admin_user.invalidate_tokens.assert_called_once()
