"""Tests for the /browse route."""


def test_browse_returns_200(client):
    """GET /browse returns 200 with HTML content."""
    resp = client.get('/browse')
    assert resp.status_code == 200
    assert 'text/html' in resp.content_type


def test_browse_no_auth_required(client):
    """GET /browse does not require Bearer token."""
    # No Authorization header — should still return 200, not 401
    resp = client.get('/browse')
    assert resp.status_code == 200


def test_browse_contains_polkadot_scripts(client):
    """Browse page includes Polkadot.js CDN scripts."""
    resp = client.get('/browse')
    html = resp.data.decode()
    assert 'polkadot/util' in html
    assert 'polkadot/extension-dapp' in html


def test_browse_contains_key_elements(client):
    """Browse page contains essential UI elements."""
    resp = client.get('/browse')
    html = resp.data.decode()
    assert 'id="login-view"' in html
    assert 'id="browse-view"' in html
    assert 'id="content-modal"' in html
    assert 'id="connect-btn"' in html


def test_browse_contains_dark_theme(client):
    """Browse page uses the dark theme CSS."""
    resp = client.get('/browse')
    html = resp.data.decode()
    assert '#1a1a2e' in html  # body background color


def test_docs_has_browse_link(client):
    """Docs page includes navigation link to /browse."""
    resp = client.get('/docs')
    html = resp.data.decode()
    assert 'href="/browse"' in html
    assert 'Browse Library' in html


def test_browse_error_and_loading_in_browse_view(client):
    """Browse-view has its own error and loading elements visible when browse-view is shown."""
    resp = client.get('/browse')
    html = resp.data.decode()
    # Error and loading elements must exist inside browse-view, not only login-view
    assert 'id="browse-error"' in html
    assert 'id="browse-loading"' in html
    # Login-view also keeps its own error/loading elements
    assert 'id="login-error"' in html
    assert 'id="login-loading"' in html


def test_browse_uses_session_endpoint(client):
    """Session restoration uses /api/auth/session, not an admin-only endpoint."""
    resp = client.get('/browse')
    html = resp.data.decode()
    assert '/api/auth/session' in html
    assert '/api/admin/config' not in html


def test_browse_copybase64_receives_event(client):
    """copyBase64 inline handler passes event explicitly for cross-browser compatibility."""
    resp = client.get('/browse')
    html = resp.data.decode()
    assert 'onclick="copyBase64(event)"' in html
    assert 'window.copyBase64 = function(event)' in html


def test_browse_pagination_state_rollback(client):
    """Pagination functions snapshot state before loadPage and roll back on failure."""
    resp = client.get('/browse')
    html = resp.data.decode()
    # nextPage should save state before mutating
    assert 'var savedCursor = state.cursor' in html
    assert 'var savedPageNum = state.pageNum' in html
    # loadPage returns a boolean
    assert 'var ok = await loadPage()' in html
    assert 'return false' in html
    assert 'return true' in html


def test_browse_load_page_returns_boolean(client):
    """loadPage function returns true on success and false on failure."""
    resp = client.get('/browse')
    html = resp.data.decode()
    # The function should have explicit return values
    assert 'return false;' in html
    assert 'return true;' in html
