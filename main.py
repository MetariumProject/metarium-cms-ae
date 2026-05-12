import logging
import os

from flask import Flask, g, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS
from google.cloud import ndb

from models.acl_models import CMSConfig, Scribe
from models.auth_models import User
from models.cms_models import CMSConflictError, CMSValidationError

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Wrap for App Engine
try:
    from google.appengine.api import wrap_wsgi_app
    app.wsgi_app = wrap_wsgi_app(app.wsgi_app)
except ImportError:
    logger.warning("google.appengine.api not available; skipping wrap_wsgi_app")

# NDB client -- project defaults to GOOGLE_CLOUD_PROJECT env var
# On App Engine, credentials are provided automatically.
# For local development, use anonymous credentials if no default credentials found.
try:
    ndb_client = ndb.Client(project=os.environ.get('GOOGLE_CLOUD_PROJECT', 'metarium-cms-ae'))
except Exception:
    import google.auth.credentials

    class _AnonymousCredentials(google.auth.credentials.Credentials):
        def refresh(self, request):
            pass

        @property
        def valid(self):
            return True

    ndb_client = ndb.Client(
        project=os.environ.get('GOOGLE_CLOUD_PROJECT', 'metarium-cms-ae'),
        credentials=_AnonymousCredentials(),
    )

# Paths that skip authentication
SKIP_AUTH_PREFIXES = ('/_ah/', '/api/auth/challenge', '/api/auth/verify', '/api/auth/refresh', '/docs', '/browse')


@app.before_request
def ndb_context_setup():
    """Set up NDB context for every request."""
    g.ndb_context = ndb_client.context()
    g.ndb_context.__enter__()


@app.before_request
def auth_middleware():
    """Authentication + ACL middleware."""
    path = request.path

    # Skip auth for specific paths
    if path == '/':
        return None
    for prefix in SKIP_AUTH_PREFIXES:
        if path.startswith(prefix):
            return None

    # Extract token from Authorization header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"error": "Authorization header required"}), 401

    token = auth_header[7:]  # Strip 'Bearer '
    if not token:
        return jsonify({"error": "Authorization header required"}), 401

    # Look up user by token
    user = User.get_by_token(token)
    if user is None:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Continuous ACL check
    if not (CMSConfig.is_admin(user.address) or Scribe.is_scribe(user.address)):
        return jsonify({"error": "Access revoked"}), 403

    g.current_user = user
    return None


@app.after_request
def set_cache_headers(response):
    """Set cache-control headers to prevent caching."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response


@app.teardown_request
def ndb_context_teardown(exception=None):
    """Clean up NDB context."""
    try:
        ctx = getattr(g, 'ndb_context', None)
        if ctx:
            ctx.__exit__(None, None, None)
    except Exception:
        logger.exception("Error cleaning up NDB context")


# --- Routes ---

@app.route('/')
def index():
    return redirect(url_for('docs'))


@app.route('/docs')
def docs():
    return render_template("docs.html")


@app.route('/browse')
def browse():
    """Browser UI for authenticated users."""
    return render_template("browse.html")


@app.route('/_ah/health')
def health():
    return jsonify({"status": "healthy"})


# --- Register Blueprints ---

from api.auth_routes import auth_bp
from api.admin_routes import admin_bp
from api.cms_routes import cms_bp
from api.graph_routes import graph_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(cms_bp, url_prefix='/api/cms')
app.register_blueprint(graph_bp, url_prefix='/api/cms')


# --- Error Handlers ---

@app.errorhandler(CMSValidationError)
def handle_validation_error(e):
    return jsonify({"error": str(e), "field": e.field}), 400


@app.errorhandler(CMSConflictError)
def handle_conflict_error(e):
    return jsonify({"error": str(e), "field": e.field, "existing_upload_id": e.existing_upload_id}), 409


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
