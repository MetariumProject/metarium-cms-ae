import logging

from flask import Blueprint, abort, g, jsonify, request
from substrateinterface import Keypair

from models.acl_models import CMSConfig, Scribe

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


def require_admin():
    """Check that the current user is the admin. Abort 403 if not."""
    if not CMSConfig.is_admin(g.current_user.address):
        abort(403, description="Admin access required")


@admin_bp.route('/scribes', methods=['POST'])
def add_scribe():
    """Add a new scribe."""
    require_admin()

    data = request.get_json(silent=True) or {}
    address = data.get('address')

    if not address:
        return jsonify({"error": "address is required"}), 400

    # Validate SS58 format
    try:
        Keypair(ss58_address=address)
    except Exception:
        return jsonify({"error": f"Invalid SS58 address: {address}"}), 400

    # Cannot add the admin address as a scribe
    if CMSConfig.is_admin(address):
        return jsonify({"error": "Cannot add admin address as a scribe"}), 400

    # Check if already a scribe
    if Scribe.is_scribe(address):
        return jsonify({"error": f"Address {address} is already a scribe"}), 409

    Scribe.create(address=address, granted_by=g.current_user.address)

    return jsonify({"message": "Scribe added", "address": address}), 201


@admin_bp.route('/scribes', methods=['DELETE'])
def remove_scribe():
    """Remove a scribe."""
    require_admin()

    data = request.get_json(silent=True) or {}
    address = data.get('address')

    if not address:
        return jsonify({"error": "address is required"}), 400

    removed = Scribe.delete_scribe(address)
    if not removed:
        return jsonify({"error": f"Scribe not found: {address}"}), 404

    return jsonify({"message": "Scribe removed", "address": address})


@admin_bp.route('/scribes', methods=['GET'])
def list_scribes():
    """List all scribes."""
    require_admin()

    scribes = Scribe.list_all()
    return jsonify({
        "scribes": [
            {
                "address": s.address,
                "granted_by": s.granted_by,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scribes
        ]
    })


@admin_bp.route('/config', methods=['GET'])
def get_config():
    """Return the CMS configuration."""
    require_admin()

    config = CMSConfig.get_config()
    if config is None:
        return jsonify({"error": "CMS not configured"}), 404

    return jsonify({
        "admin_address": config.admin_address,
        "created_at": config.created_at.isoformat() if config.created_at else None,
    })
