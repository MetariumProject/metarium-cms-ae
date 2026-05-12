"""Unit tests for model validators and graph predicates."""
import pytest

from models.cms_models import CMSUpload, CMSValidationError
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
