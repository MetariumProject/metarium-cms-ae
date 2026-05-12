"""Unit tests for /api/cms/<series>/<upload_id>/graph/* endpoints."""
from unittest import mock

import pytest

from tests.conftest import ADMIN_ADDRESS


def _mock_upload(upload_id=1, uuid_val="aaaa-bbbb-cccc-dddd", series="test-series"):
    """Return a MagicMock that looks like a CMSUpload."""
    u = mock.MagicMock()
    u.upload_id = upload_id
    u.uuid = uuid_val
    u.series = series
    u.content_type = "application/octet-stream"
    u.lookup_path = None
    u.key = mock.MagicMock()
    return u


def _mock_relationship(rel_id=100, source_uuid="aaaa-bbbb-cccc-dddd",
                        predicate="rel:relatedTo", target_uuid="xxxx-yyyy",
                        status="active"):
    """Return a MagicMock that looks like a CMSRelationship."""
    r = mock.MagicMock()
    r.key = mock.MagicMock()
    r.key.id.return_value = rel_id
    r.source_uuid = source_uuid
    r.predicate = predicate
    r.target_uuid = target_uuid
    r.target_series = "test-series"
    r.target_content_type = "application/octet-stream"
    r.target_lookup_path = None
    r.status = status
    r.created_by = ADMIN_ADDRESS
    r.created_at = None
    r.last_updated = None
    r.to_dict.return_value = {
        "relationship_id": rel_id,
        "source_uuid": source_uuid,
        "predicate": predicate,
        "target_uuid": target_uuid,
        "target_series": "test-series",
        "target_content_type": "application/octet-stream",
        "target_lookup_path": None,
        "status": status,
        "created_by": ADMIN_ADDRESS,
        "created_at": None,
        "last_updated": None,
    }
    return r


# ---------------------------------------------------------------------------
# POST /<series>/<upload_id>/graph/add
# ---------------------------------------------------------------------------

class TestGraphAdd:

    def test_add_relationship(self, client, mock_admin_user, admin_headers):
        """Successfully add relationship => 201."""
        source = _mock_upload()
        target = _mock_upload(upload_id=2, uuid_val="xxxx-yyyy", series="test-series")
        rel = _mock_relationship()

        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.validate_predicate", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_uuid", return_value=target), \
             mock.patch("api.graph_routes.CMSRelationship.create_relationship", return_value=rel):

            resp = client.post("/api/cms/test-series/1/graph/add", headers=admin_headers, json={
                "predicate": "rel:relatedTo",
                "target_uuid": "xxxx-yyyy",
            })
            assert resp.status_code == 201
            assert "relationship" in resp.get_json()

    def test_add_invalid_predicate(self, client, mock_admin_user, admin_headers):
        """Invalid predicate => 400 with allowed_predicates."""
        source = _mock_upload()
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.validate_predicate", return_value=False):

            resp = client.post("/api/cms/test-series/1/graph/add", headers=admin_headers, json={
                "predicate": "invalid:pred",
                "target_uuid": "xxxx-yyyy",
            })
            assert resp.status_code == 400
            assert "allowed_predicates" in resp.get_json()

    def test_add_target_not_found(self, client, mock_admin_user, admin_headers):
        """Target UUID doesn't exist => 404."""
        source = _mock_upload()
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.validate_predicate", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_uuid", return_value=None):

            resp = client.post("/api/cms/test-series/1/graph/add", headers=admin_headers, json={
                "predicate": "rel:relatedTo",
                "target_uuid": "nonexistent",
            })
            assert resp.status_code == 404

    def test_add_self_link(self, client, mock_admin_user, admin_headers):
        """Cannot link upload to itself => 400."""
        source = _mock_upload(uuid_val="same-uuid")
        target = _mock_upload(uuid_val="same-uuid")
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.validate_predicate", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_uuid", return_value=target):

            resp = client.post("/api/cms/test-series/1/graph/add", headers=admin_headers, json={
                "predicate": "rel:relatedTo",
                "target_uuid": "same-uuid",
            })
            assert resp.status_code == 400

    def test_add_source_not_found(self, client, mock_admin_user, admin_headers):
        """Source upload doesn't exist => 404."""
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=None):

            resp = client.post("/api/cms/test-series/999/graph/add", headers=admin_headers, json={
                "predicate": "rel:relatedTo",
                "target_uuid": "xxxx-yyyy",
            })
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /<series>/<upload_id>/graph/list
# ---------------------------------------------------------------------------

class TestGraphList:

    def test_list_active(self, client, mock_admin_user, admin_headers):
        """List active relationships => 200."""
        source = _mock_upload()
        rel = _mock_relationship()
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.list_by_source", return_value=[rel]):

            resp = client.get("/api/cms/test-series/1/graph/list", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["relationships"]) == 1

    def test_list_empty(self, client, mock_admin_user, admin_headers):
        """List with no relationships => 200 with empty list."""
        source = _mock_upload()
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.list_by_source", return_value=[]):

            resp = client.get("/api/cms/test-series/1/graph/list", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.get_json()["relationships"] == []


# ---------------------------------------------------------------------------
# POST /<series>/<upload_id>/graph/remove
# ---------------------------------------------------------------------------

class TestGraphRemove:

    def test_remove_relationship(self, client, mock_admin_user, admin_headers):
        """Remove active relationship => 200."""
        source = _mock_upload()
        rel = _mock_relationship(status="active")
        rel.remove = mock.MagicMock()
        # After remove() the to_dict should show 'removed'
        rel.to_dict.return_value["status"] = "removed"

        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.get_by_id_and_parent", return_value=rel):

            resp = client.post("/api/cms/test-series/1/graph/remove", headers=admin_headers, json={
                "relationship_id": 100,
            })
            assert resp.status_code == 200

    def test_remove_nonexistent(self, client, mock_admin_user, admin_headers):
        """Relationship not found => 404."""
        source = _mock_upload()
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.get_by_id_and_parent", return_value=None):

            resp = client.post("/api/cms/test-series/1/graph/remove", headers=admin_headers, json={
                "relationship_id": 999,
            })
            assert resp.status_code == 404

    def test_remove_already_removed(self, client, mock_admin_user, admin_headers):
        """Relationship already removed => 400."""
        source = _mock_upload()
        rel = _mock_relationship(status="removed")

        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.get_by_id_and_parent", return_value=rel):

            resp = client.post("/api/cms/test-series/1/graph/remove", headers=admin_headers, json={
                "relationship_id": 100,
            })
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /<series>/<upload_id>/graph/removed
# ---------------------------------------------------------------------------

class TestGraphRemoved:

    def test_list_removed(self, client, mock_admin_user, admin_headers):
        """List removed relationships => 200."""
        source = _mock_upload()
        rel = _mock_relationship(status="removed")
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_upload_id", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.list_by_source", return_value=[rel]):

            resp = client.get("/api/cms/test-series/1/graph/removed", headers=admin_headers)
            assert resp.status_code == 200
            assert len(resp.get_json()["relationships"]) == 1


# ---------------------------------------------------------------------------
# GET /<series>/graph/uuid/<uuid>
# ---------------------------------------------------------------------------

class TestGraphByUuid:

    def test_list_by_uuid(self, client, mock_admin_user, admin_headers):
        """Active relationships by UUID => 200."""
        source = _mock_upload()
        rel = _mock_relationship()
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_uuid", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.list_by_source", return_value=[rel]):

            resp = client.get(f"/api/cms/test-series/graph/uuid/{source.uuid}", headers=admin_headers)
            assert resp.status_code == 200

    def test_list_by_uuid_wrong_series(self, client, mock_admin_user, admin_headers):
        """UUID exists but wrong series => 404."""
        source = _mock_upload(series="other-series")
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_uuid", return_value=source):

            resp = client.get(f"/api/cms/test-series/graph/uuid/{source.uuid}", headers=admin_headers)
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /<series>/graph/uuid/<uuid>/removed
# ---------------------------------------------------------------------------

class TestGraphByUuidRemoved:

    def test_list_removed_by_uuid(self, client, mock_admin_user, admin_headers):
        """Removed relationships by UUID => 200."""
        source = _mock_upload()
        rel = _mock_relationship(status="removed")
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True), \
             mock.patch("api.graph_routes.CMSUpload.get_by_uuid", return_value=source), \
             mock.patch("api.graph_routes.CMSRelationship.list_by_source", return_value=[rel]):

            resp = client.get(f"/api/cms/test-series/graph/uuid/{source.uuid}/removed", headers=admin_headers)
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /<series>/<upload_id>/graph/predicates
# ---------------------------------------------------------------------------

class TestGraphPredicates:

    def test_get_predicates(self, client, mock_admin_user, admin_headers):
        """Get predicate dictionary => 200."""
        with mock.patch("api.graph_routes.CMSUpload.validate_series", return_value=True):
            resp = client.get("/api/cms/test-series/1/graph/predicates", headers=admin_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "predicates" in data
            # Should have all namespace keys
            assert "owl" in data["predicates"]
            assert "rel" in data["predicates"]
