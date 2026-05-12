"""Shared pytest fixtures for metarium-cms-ae tests."""
import sys
import types
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Pre-import patching: mock google.appengine.api BEFORE any app code loads
# ---------------------------------------------------------------------------
_appengine_api_mod = types.ModuleType("google.appengine.api")
_appengine_api_mod.wrap_wsgi_app = lambda wsgi_app, **kw: wsgi_app
_appengine_mod = types.ModuleType("google.appengine")
_appengine_mod.api = _appengine_api_mod

sys.modules.setdefault("google.appengine", _appengine_mod)
sys.modules.setdefault("google.appengine.api", _appengine_api_mod)


# ---------------------------------------------------------------------------
# 1. App fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Create Flask app with NDB client mocked."""
    with mock.patch("google.cloud.ndb.Client") as MockNdbClient:
        mock_ctx = mock.MagicMock()
        mock_ctx.__enter__ = mock.MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = mock.MagicMock(return_value=False)
        MockNdbClient.return_value.context.return_value = mock_ctx

        # Force re-creation: remove cached main module so ndb.Client patch takes effect
        for mod_name in list(sys.modules):
            if mod_name == "main":
                del sys.modules[mod_name]

        import main  # noqa: F811
        main.app.config["TESTING"] = True
        # Replace the ndb_client so before_request handler uses the mock
        main.ndb_client = MockNdbClient.return_value

        yield main.app


# ---------------------------------------------------------------------------
# 2. Test client
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# 3. Header helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_headers():
    return {"Authorization": "Bearer admin-test-token", "Content-Type": "application/json"}


@pytest.fixture()
def scribe_headers():
    return {"Authorization": "Bearer scribe-test-token", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# 4. Addresses
# ---------------------------------------------------------------------------

ADMIN_ADDRESS = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
SCRIBE_ADDRESS = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


# ---------------------------------------------------------------------------
# 5. Mock users
# ---------------------------------------------------------------------------

def _make_mock_user(address):
    user = mock.MagicMock()
    user.address = address
    user.invalidate_tokens = mock.MagicMock()
    return user


@pytest.fixture()
def mock_admin_user():
    """Patch auth middleware to recognise an admin bearer token."""
    user = _make_mock_user(ADMIN_ADDRESS)
    with mock.patch("models.auth_models.User.get_by_token", return_value=user), \
         mock.patch("models.acl_models.CMSConfig.is_admin", side_effect=lambda addr: addr == ADMIN_ADDRESS), \
         mock.patch("models.acl_models.Scribe.is_scribe", return_value=False):
        yield user


@pytest.fixture()
def mock_scribe_user():
    """Patch auth middleware to recognise a scribe bearer token."""
    user = _make_mock_user(SCRIBE_ADDRESS)
    with mock.patch("models.auth_models.User.get_by_token", return_value=user), \
         mock.patch("models.acl_models.CMSConfig.is_admin", return_value=False), \
         mock.patch("models.acl_models.Scribe.is_scribe", side_effect=lambda addr: addr == SCRIBE_ADDRESS):
        yield user
