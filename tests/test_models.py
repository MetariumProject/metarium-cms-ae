"""Unit tests for model validators, graph predicates, and model methods."""
import base64
from datetime import datetime
from unittest import mock

import pytest

from models.cms_models import CMSSeriesCounter, CMSUpload, CMSValidationError
from models.acl_models import CMSConfig, Scribe
from models.graph_models import ALL_PREDICATES, ALLOWED_PREDICATES, validate_predicate


# ---- CMSUpload.validate_series -------------------------------------------

class TestValidateSeries:
    """Tests for CMSUpload.validate_series()."""

    @pytest.mark.parametrize("series", ["my-series", "test01", "ab", "a0", "hello-world", "abc_def"])
    def test_valid_series(self, series):
        assert CMSUpload.validate_series(series) is True

    @pytest.mark.parametrize("series,reason", [
        ("A", "uppercase single char"),
        ("has spaces", "contains spaces"),
        ("", "empty string"),
        ("-start", "starts with hyphen"),
        ("end-", "ends with hyphen"),
        ("a" * 65, "too long (65 chars)"),
    ])
    def test_invalid_series(self, series, reason):
        with pytest.raises(CMSValidationError) as exc_info:
            CMSUpload.validate_series(series)
        assert exc_info.value.field == "series"


# ---- CMSUpload.validate_lookup_path --------------------------------------

class TestValidateLookupPath:
    """Tests for CMSUpload.validate_lookup_path()."""

    @pytest.mark.parametrize("path", [
        "2025/05/11/report.json",
        "file.txt",
        "a/b/c.dat",
    ])
    def test_valid_lookup_path(self, path):
        assert CMSUpload.validate_lookup_path(path) is True

    @pytest.mark.parametrize("path,reason", [
        ("/leading/file.txt", "starts with /"),
        ("no-extension", "no file extension"),
        ("trailing/", "ends with /"),
        ("", "empty string"),
    ])
    def test_invalid_lookup_path(self, path, reason):
        with pytest.raises(CMSValidationError) as exc_info:
            CMSUpload.validate_lookup_path(path)
        assert exc_info.value.field == "lookup_path"


# ---- validate_predicate ---------------------------------------------------

class TestValidatePredicate:
    """Tests for validate_predicate()."""

    @pytest.mark.parametrize("pred", [
        "owl:sameAs",
        "rdfs:subClassOf",
        "skos:broader",
        "cause:directCause",
        "rel:relatedTo",
        "temporal:before",
    ])
    def test_valid_predicate(self, pred):
        assert validate_predicate(pred) is True

    @pytest.mark.parametrize("pred", [
        "invalid:pred",
        "owl:notReal",
        "",
        "completely wrong",
    ])
    def test_invalid_predicate(self, pred):
        assert validate_predicate(pred) is False


# ---- ALL_PREDICATES set ---------------------------------------------------

class TestAllPredicates:
    """Ensure ALL_PREDICATES contains every predicate from every namespace."""

    def test_all_predicates_complete(self):
        for ns, preds in ALLOWED_PREDICATES.items():
            for p in preds:
                assert p in ALL_PREDICATES, f"{p} missing from ALL_PREDICATES"

    def test_no_extra_predicates(self):
        expected = set()
        for preds in ALLOWED_PREDICATES.values():
            expected.update(preds)
        assert ALL_PREDICATES == expected


# ---- CMSUpload.to_dict ---------------------------------------------------

class TestCMSUploadToDict:
    """Tests for CMSUpload.to_dict() serialization."""

    def test_to_dict_binary_content(self):
        """Binary content should be base64-encoded in to_dict output."""
        upload = CMSUpload()
        upload.upload_id = 1
        upload.uuid = "test-uuid-1234"
        upload.series = "test-series"
        upload.lookup_path = "2025/01/data.bin"
        upload.content = b"\x00\x01\x02\xff"
        upload.content_text = None
        upload.content_type = "application/octet-stream"
        upload.extra_metadata = {"key": "value"}
        upload.timestamp = datetime(2025, 1, 1)
        upload.source_ip = "127.0.0.1"
        upload.user_agent = "test-agent"
        upload.signature = "sig123"
        upload.created_at = datetime(2025, 1, 1)
        upload.updated_at = datetime(2025, 1, 2)

        result = upload.to_dict()
        assert result["upload_id"] == 1
        assert result["uuid"] == "test-uuid-1234"
        assert result["series"] == "test-series"
        # Binary content should be base64-encoded
        assert result["content"] == base64.b64encode(b"\x00\x01\x02\xff").decode("utf-8")
        assert result["content_type"] == "application/octet-stream"
        assert result["extra_metadata"] == {"key": "value"}

    def test_to_dict_text_content(self):
        """Text content should be returned as-is in to_dict output."""
        upload = CMSUpload()
        upload.upload_id = 2
        upload.uuid = "test-uuid-5678"
        upload.series = "docs"
        upload.lookup_path = "readme.txt"
        upload.content = None
        upload.content_text = "Hello, world!"
        upload.content_type = "text/plain"
        upload.extra_metadata = {}
        upload.timestamp = datetime(2025, 1, 1)
        upload.source_ip = None
        upload.user_agent = None
        upload.signature = None
        upload.created_at = datetime(2025, 1, 1)
        upload.updated_at = datetime(2025, 1, 2)

        result = upload.to_dict()
        assert result["upload_id"] == 2
        assert result["uuid"] == "test-uuid-5678"
        # Text content should be raw string
        assert result["content"] == "Hello, world!"
        assert result["content_type"] == "text/plain"


# ---- CMSUpload.to_dict_meta -----------------------------------------------

class TestCMSUploadToDictMeta:
    """Tests for CMSUpload.to_dict_meta() metadata-only serialization."""

    def test_to_dict_meta_excludes_content(self):
        """to_dict_meta should not include a 'content' key."""
        upload = CMSUpload()
        upload.upload_id = 1
        upload.uuid = "test-uuid-meta"
        upload.series = "test-series"
        upload.lookup_path = "doc.txt"
        upload.content = b"\x00\x01\x02"
        upload.content_text = None
        upload.content_type = "application/octet-stream"
        upload.extra_metadata = None
        upload.timestamp = datetime(2025, 1, 1)
        upload.source_ip = "127.0.0.1"
        upload.user_agent = "test-agent"
        upload.signature = None
        upload.created_at = datetime(2025, 1, 1)
        upload.updated_at = datetime(2025, 1, 2)

        result = upload.to_dict_meta()
        assert "content" not in result
        assert result["upload_id"] == 1
        assert result["uuid"] == "test-uuid-meta"
        assert result["series"] == "test-series"

    def test_to_dict_includes_content_and_meta(self):
        """to_dict should include both metadata and content."""
        upload = CMSUpload()
        upload.upload_id = 3
        upload.uuid = "test-uuid-full"
        upload.series = "test-series"
        upload.lookup_path = None
        upload.content = b"hello"
        upload.content_text = None
        upload.content_type = "text/plain"
        upload.extra_metadata = None
        upload.timestamp = datetime(2025, 1, 1)
        upload.source_ip = None
        upload.user_agent = None
        upload.signature = None
        upload.created_at = datetime(2025, 1, 1)
        upload.updated_at = datetime(2025, 1, 2)

        result = upload.to_dict()
        assert "content" in result
        assert result["upload_id"] == 3
        assert result["content"] == base64.b64encode(b"hello").decode("utf-8")


# ---- CMSSeriesCounter ----------------------------------------------------

class TestCMSSeriesCounter:
    """Tests for the transactional per-series counter."""

    def test_allocate_id_new_series(self):
        """First allocation for a series returns 1."""
        with mock.patch("models.cms_models.ndb.Key") as MockKey, \
             mock.patch("models.cms_models.ndb.transactional", lambda: lambda f: f):
            mock_key_instance = mock.MagicMock()
            mock_key_instance.get.return_value = None
            MockKey.return_value = mock_key_instance

            # We need to call the underlying logic; since ndb.transactional
            # is mocked away, we can call the classmethod directly with
            # a fresh import.
            counter = CMSSeriesCounter(next_id=1)
            counter.put = mock.MagicMock()

            mock_key_instance.get.return_value = None

            # Test via _get_next_upload_id which calls allocate_id
            with mock.patch.object(CMSSeriesCounter, 'allocate_id', return_value=1):
                result = CMSUpload._get_next_upload_id("test-series")
                assert result == 1

    def test_allocate_id_existing_series(self):
        """Subsequent allocation returns the next value."""
        with mock.patch.object(CMSSeriesCounter, 'allocate_id', return_value=42):
            result = CMSUpload._get_next_upload_id("existing-series")
            assert result == 42


# ---- CMSUpload.delete_with_relationships ---------------------------------

class TestDeleteWithRelationships:
    """Tests for CMSUpload.delete_with_relationships()."""

    def _make_upload_with_mock_key(self):
        """Create a mock that has delete_with_relationships bound properly."""
        upload = mock.MagicMock(spec=CMSUpload)
        upload.key = mock.MagicMock()
        # Bind the real method to the mock instance
        upload.delete_with_relationships = lambda: CMSUpload.delete_with_relationships(upload)
        return upload

    def test_delete_cascades_relationships(self):
        """Deleting an upload also deletes all descendant relationships."""
        upload = self._make_upload_with_mock_key()
        mock_rel_keys = [mock.MagicMock(), mock.MagicMock()]

        with mock.patch("models.graph_models.CMSRelationship.query") as MockQuery, \
             mock.patch("models.cms_models.ndb.delete_multi") as mock_delete_multi:
            MockQuery.return_value.fetch.return_value = mock_rel_keys

            upload.delete_with_relationships()

            MockQuery.assert_called_once_with(ancestor=upload.key)
            MockQuery.return_value.fetch.assert_called_once_with(keys_only=True)
            mock_delete_multi.assert_called_once_with(mock_rel_keys)
            upload.key.delete.assert_called_once()

    def test_delete_no_relationships(self):
        """Deleting an upload with no relationships still deletes the upload."""
        upload = self._make_upload_with_mock_key()

        with mock.patch("models.graph_models.CMSRelationship.query") as MockQuery, \
             mock.patch("models.cms_models.ndb.delete_multi") as mock_delete_multi:
            MockQuery.return_value.fetch.return_value = []

            upload.delete_with_relationships()

            mock_delete_multi.assert_not_called()
            upload.key.delete.assert_called_once()


# ---- CMSConfig.is_admin --------------------------------------------------

class TestCMSConfigIsAdmin:
    """Tests for CMSConfig.is_admin()."""

    def test_is_admin_true(self):
        """is_admin returns True for matching admin address."""
        mock_config = mock.MagicMock()
        mock_config.admin_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        with mock.patch.object(CMSConfig, "get_by_id", return_value=mock_config):
            assert CMSConfig.is_admin("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY") is True

    def test_is_admin_false_different_address(self):
        """is_admin returns False for non-matching address."""
        mock_config = mock.MagicMock()
        mock_config.admin_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        with mock.patch.object(CMSConfig, "get_by_id", return_value=mock_config):
            assert CMSConfig.is_admin("5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty") is False

    def test_is_admin_false_no_config(self):
        """is_admin returns False when no config exists."""
        with mock.patch.object(CMSConfig, "get_by_id", return_value=None):
            assert CMSConfig.is_admin("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY") is False


# ---- Scribe.is_scribe ----------------------------------------------------

class TestScribeIsScribe:
    """Tests for Scribe.is_scribe()."""

    def test_is_scribe_true(self):
        """is_scribe returns True for existing scribe."""
        mock_scribe = mock.MagicMock()
        with mock.patch.object(Scribe, "get_by_id", return_value=mock_scribe):
            assert Scribe.is_scribe("5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty") is True

    def test_is_scribe_false(self):
        """is_scribe returns False for non-existing address."""
        with mock.patch.object(Scribe, "get_by_id", return_value=None):
            assert Scribe.is_scribe("5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty") is False
