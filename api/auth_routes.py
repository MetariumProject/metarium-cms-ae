import json
import time
from uuid import uuid4

from flask import Blueprint, g, jsonify, request
from substrateinterface import Keypair

from models.acl_models import CMSConfig, Scribe
from models.auth_models import Challenge, User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/challenge', methods=['POST'])
def challenge():
    """Generate an authentication challenge for a given SS58 address."""
    data = request.get_json(silent=True) or {}
    address = data.get('address')

    if not address:
        return jsonify({"error": "address is required"}), 400

    # Validate SS58 address
    try:
        Keypair(ss58_address=address)
    except Exception:
        return jsonify({"error": f"Invalid SS58 address: {address}"}), 400

    # Verify the address is authorized (admin or scribe)
    if not (CMSConfig.is_admin(address) or Scribe.is_scribe(address)):
        return jsonify({"error": "Not authorized. Must be admin or scribe."}), 403

    # Generate challenge
    challenge_data = {
        "address": address,
        "timestamp": int(time.time()),
        "nonce": str(uuid4()),
        "message": "Sign this message to authenticate with Metarium CMS",
    }

    Challenge.store_challenge(address, challenge_data)

    return jsonify({"challenge": challenge_data})


@auth_bp.route('/verify', methods=['POST'])
def verify():
    """Verify a signed challenge and issue tokens."""
    data = request.get_json(silent=True) or {}
    address = data.get('address')
    message = data.get('message')
    signature = data.get('signature')

    if not all([address, message, signature]):
        return jsonify({"error": "address, message, and signature are required"}), 400

    # Get the stored challenge
    stored_challenge = Challenge.get_challenge(address)
    if stored_challenge is None:
        return jsonify({"error": "No valid challenge found. Request a new one."}), 400

    # Decode hex (strip 0x prefix)
    try:
        message_bytes = bytes.fromhex(message.replace('0x', ''))
        signature_bytes = bytes.fromhex(signature.replace('0x', ''))
    except ValueError:
        return jsonify({"error": "Invalid hex encoding for message or signature"}), 400

    # Verify signature
    try:
        keypair = Keypair(ss58_address=address)
        is_valid = keypair.verify(message_bytes, signature_bytes)
    except Exception:
        return jsonify({"error": "Signature verification failed"}), 401

    if not is_valid:
        return jsonify({"error": "Signature verification failed"}), 401

    # Decode message bytes to JSON and compare against stored challenge data
    try:
        decoded_message = json.loads(message_bytes.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({"error": "Invalid message format"}), 401

    if decoded_message != stored_challenge.challenge_data:
        return jsonify({"error": "Challenge data mismatch"}), 401

    # Clear challenge, create/get user, generate tokens
    Challenge.clear_challenge(address)
    user = User.create_or_update(address)
    tokens = user.generate_tokens()

    # Determine role
    if CMSConfig.is_admin(address):
        role = "admin"
    elif Scribe.is_scribe(address):
        role = "scribe"
    else:
        role = "unknown"

    return jsonify({
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": 3600,
        "role": role,
        "address": address,
    })


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token using a valid refresh token."""
    data = request.get_json(silent=True) or {}
    refresh_token = data.get('refresh_token')

    if not refresh_token:
        return jsonify({"error": "refresh_token is required"}), 400

    user = User.get_by_refresh_token(refresh_token)
    if user is None:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    # Re-check ACL
    if not (CMSConfig.is_admin(user.address) or Scribe.is_scribe(user.address)):
        user.invalidate_tokens()
        return jsonify({"error": "Access revoked"}), 403

    tokens = user.generate_tokens()

    # Determine role
    if CMSConfig.is_admin(user.address):
        role = "admin"
    elif Scribe.is_scribe(user.address):
        role = "scribe"
    else:
        role = "unknown"

    return jsonify({
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": 3600,
        "role": role,
        "address": user.address,
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Invalidate the current user's tokens."""
    g.current_user.invalidate_tokens()
    return jsonify({"message": "Logged out"})
