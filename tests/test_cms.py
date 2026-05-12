"""Unit tests for /api/cms/* endpoints."""
import base64
from unittest import mock

import pytest

from models.cms_models import CMSConflictError, CMSValidationError
from tests.conftest import ADMIN_ADDRESS, SCRIBE_ADDRESS


def _mock_upload(upload_id=1, uuid_val="aaaa-bbbb-cccc-dddd", series="test-series",
                 content=b"hello", content_text=None, content_type="application/octet-stream",
                 lookup_path=None):
    """Build a mock CMSUpload entity."""
    u = mock.MagicMock()
    u.upload_id = upload_id
    u.uuid = uuid_val
    u.series = series
    u.lookup_path = lookup_path
    u.content = content
    u.content_text = content_text
    u.content_type = content_type
    u.extra_metadata = None
    u.source_ip = "127.0.0.1"
    u.user_agent = "test"
    u.signature = None
    u.created_at = None
    u.updated_at = None
    u.timestamp = None
    meta = {
        "upload_id": upload_id,
        "uuid": uuid_val,
        "series": series,
        "lookup_path": lookup_path,
        "content_type": content_type,
        "extra_metadata": None,
        "source_ip": "127.0.0.1",
        "user_agent": "test",
        "signature": None,
        "created_at": None,
        "updated_at": None,
        "timestamp": None,
    }
    u.to_dict_meta.return_value = meta
    u.to_dict.return_value = {
        **meta,
        "content": base64.b64encode(content).decode() if content else content_text,
    }
    u.key = mock.MagicMock()
    return u


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------

class TestUpload:

    def test_upload_binary(self, client, mock_admin_user, admin_headers):
        """Binary upload => 201 with upload_id and uuid."""
        upload = _mock_upload()
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.create_upload", return_value=upload):

            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content": base64.b64encode(b"hello world").decode(),
                "content_type": "application/octet-stream",
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert "upload_id" in data
            assert "uuid" in data

    def test_upload_text(self, client, mock_admin_user, admin_headers):
        """Text upload => 201."""
        upload = _mock_upload(content=None, content_text="hello text")
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.create_upload", return_value=upload):

            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content_text": "hello text",
                "content_type": "text/plain",
            })
            assert resp.status_code == 201

    def test_upload_with_lookup_path(self, client, mock_admin_user, admin_headers):
        """Upload with lookup_path => 201."""
        upload = _mock_upload(lookup_path="2025/05/report.json")
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.create_upload", return_value=upload):

            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content": base64.b64encode(b"data").decode(),
                "content_type": "application/json",
                "lookup_path": "2025/05/report.json",
            })
            assert resp.status_code == 201
            assert resp.get_json()["lookup_path"] == "2025/05/report.json"

    def test_upload_missing_content(self, client, mock_admin_user, admin_headers):
        """Neither content nor content_text => 400."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True):
            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content_type": "text/plain",
            })
            assert resp.status_code == 400

    def test_upload_invalid_base64(self, client, mock_admin_user, admin_headers):
        """Invalid base64 => 400."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True):
            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content": "!!!not-base64!!!",
                "content_type": "application/octet-stream",
            })
            assert resp.status_code == 400

    def test_upload_oversized(self, client, mock_admin_user, admin_headers):
        """Content > 1 MB => 413 (Request Entity Too Large)."""
        big_data = base64.b64encode(b"x" * (1024 * 1024 + 1)).decode()
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True):
            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content": big_data,
                "content_type": "application/octet-stream",
            })
            assert resp.status_code == 413

    def test_upload_text_oversized(self, client, mock_admin_user, admin_headers):
        """Text content > 1 MB => 413."""
        big_text = "x" * (1024 * 1024 + 1)
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True):
            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content_text": big_text,
                "content_type": "text/plain",
            })
            assert resp.status_code == 413

    def test_upload_both_content_fields(self, client, mock_admin_user, admin_headers):
        """Providing both content and content_text => 400."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True):
            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content": base64.b64encode(b"binary").decode(),
                "content_text": "text",
                "content_type": "application/octet-stream",
            })
            assert resp.status_code == 400
            assert "not both" in resp.get_json()["error"]

    def test_upload_duplicate_lookup_path(self, client, mock_admin_user, admin_headers):
        """Duplicate lookup_path => 409."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.create_upload",
                        side_effect=CMSConflictError("exists", field="lookup_path",
                                                     existing_upload_id=1)):
            resp = client.post("/api/cms/test-series/upload", headers=admin_headers, json={
                "content": base64.b64encode(b"data").decode(),
                "content_type": "application/json",
                "lookup_path": "dup/file.json",
            })
            assert resp.status_code == 409

    def test_upload_invalid_series(self, client, mock_admin_user, admin_headers):
        """Invalid series name => 400."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series",
                        side_effect=CMSValidationError("bad series", field="series")):
            resp = client.post("/api/cms/BAD-SERIES/upload", headers=admin_headers, json={
                "content": base64.b64encode(b"data").decode(),
                "content_type": "application/json",
            })
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Download tests
# ---------------------------------------------------------------------------

class TestDownload:

    def test_download_by_id(self, client, mock_admin_user, admin_headers):
        """Get by upload_id => 200."""
        upload = _mock_upload()
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_upload_id", return_value=upload):
            resp = client.get("/api/cms/test-series/download/1", headers=admin_headers)
            assert resp.status_code == 200
            assert "data" in resp.get_json()

    def test_download_by_id_not_found(self, client, mock_admin_user, admin_headers):
        """Upload id not found => 404."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_upload_id", return_value=None):
            resp = client.get("/api/cms/test-series/download/999", headers=admin_headers)
            assert resp.status_code == 404

    def test_download_by_uuid(self, client, mock_admin_user, admin_headers):
        """Get by UUID => 200."""
        upload = _mock_upload()
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_uuid", return_value=upload):
            resp = client.get(f"/api/cms/test-series/uuid/{upload.uuid}", headers=admin_headers)
            assert resp.status_code == 200

    def test_download_by_uuid_wrong_series(self, client, mock_admin_user, admin_headers):
        """UUID exists but in a different series => 404."""
        upload = _mock_upload(series="other-series")
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_uuid", return_value=upload):
            resp = client.get(f"/api/cms/test-series/uuid/{upload.uuid}", headers=admin_headers)
            assert resp.status_code == 404

    def test_download_by_path(self, client, mock_admin_user, admin_headers):
        """Get by lookup_path => 200."""
        upload = _mock_upload(lookup_path="2025/05/report.json")
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_lookup_path", return_value=upload):
            resp = client.get("/api/cms/test-series/path/2025/05/report.json", headers=admin_headers)
            assert resp.status_code == 200

    def test_download_by_path_not_found(self, client, mock_admin_user, admin_headers):
        """lookup_path not found => 404."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_lookup_path", return_value=None):
            resp = client.get("/api/cms/test-series/path/missing/file.txt", headers=admin_headers)
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

class TestList:

    def test_list_with_cursor(self, client, mock_admin_user, admin_headers):
        """List uploads => 200 with uploads array (metadata only, no content)."""
        upload = _mock_upload()
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.list_by_series", return_value=([upload], None)):
            resp = client.get("/api/cms/test-series/list?limit=10", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "uploads" in data
            assert data["series"] == "test-series"
            # List endpoint returns metadata only, no content
            assert "content" not in data["uploads"][0]
            upload.to_dict_meta.assert_called_once()

    def test_list_invalid_limit(self, client, mock_admin_user, admin_headers):
        """Non-integer limit => 400."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True):
            resp = client.get("/api/cms/test-series/list?limit=abc", headers=admin_headers)
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------

class TestDelete:

    def test_delete_as_admin(self, client, mock_admin_user, admin_headers):
        """Admin can delete => 200, cascade-deletes relationships."""
        upload = _mock_upload()
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSConfig.is_admin", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_upload_id", return_value=upload):
            resp = client.delete("/api/cms/test-series/delete/1", headers=admin_headers)
            assert resp.status_code == 200
            upload.delete_with_relationships.assert_called_once()

    def test_delete_as_scribe(self, client, mock_scribe_user, scribe_headers):
        """Scribe cannot delete => 403."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSConfig.is_admin", return_value=False):
            resp = client.delete("/api/cms/test-series/delete/1", headers=scribe_headers)
            assert resp.status_code == 403

    def test_delete_not_found(self, client, mock_admin_user, admin_headers):
        """Delete non-existent upload => 404."""
        with mock.patch("api.cms_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.cms_routes.CMSConfig.is_admin", return_value=True), \
             mock.patch("api.cms_routes.CMSUpload.get_by_upload_id", return_value=None):
            resp = client.delete("/api/cms/test-series/delete/999", headers=admin_headers)
            assert resp.status_code == 404
