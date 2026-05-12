import base64
import logging

from flask import Blueprint, g, jsonify, request

from models.acl_models import CMSConfig
from models.cms_models import CMSConflictError, CMSUpload, CMSValidationError

logger = logging.getLogger(__name__)

cms_bp = Blueprint('cms', __name__)


@cms_bp.route('/<series>/upload', methods=['POST'])
def upload(series):
    """Upload content to a series."""
    # Validate series
    try:
        CMSUpload.validate_series(series)
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400

    data = request.get_json(silent=True) or {}

    content_b64 = data.get('content')
    content_text = data.get('content_text')
    content_type = data.get('content_type')
    lookup_path = data.get('lookup_path')
    extra_metadata = data.get('extra_metadata')
    signature = data.get('signature')

    # Validate: need exactly one content field
    if not content_b64 and not content_text:
        return jsonify({"error": "Either 'content' (base64) or 'content_text' is required"}), 400

    if content_b64 and content_text:
        return jsonify({"error": "Provide either 'content' (base64) or 'content_text', not both"}), 400

    # Validate: content_type is required
    if not content_type:
        return jsonify({"error": "content_type is required"}), 400

    MAX_CONTENT_BYTES = 1 * 1024 * 1024  # 1 MB

    # Decode binary content if provided
    content_bytes = None
    if content_b64:
        try:
            content_bytes = base64.b64decode(content_b64, validate=True)
        except Exception:
            return jsonify({"error": "Invalid base64 encoding in 'content' field"}), 400

        # Check size limit: 1MB
        if len(content_bytes) > MAX_CONTENT_BYTES:
            return jsonify({"error": "Content exceeds maximum size of 1MB"}), 413

    # Validate text content size
    if content_text:
        if len(content_text.encode('utf-8')) > MAX_CONTENT_BYTES:
            return jsonify({"error": "Content text exceeds maximum size of 1MB"}), 413

    # If signature provided, validate informally (log, don't reject)
    if signature:
        logger.info("Upload includes signature: %s (informational only)", signature[:20] if len(signature) > 20 else signature)

    # Gather request metadata
    source_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')

    try:
        upload_entity = CMSUpload.create_upload(
            series=series,
            content_bytes=content_bytes,
            content_text=content_text,
            content_type=content_type,
            extra_metadata=extra_metadata,
            lookup_path=lookup_path,
            source_ip=source_ip,
            user_agent=user_agent,
            signature=signature,
        )
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400
    except CMSConflictError as e:
        return jsonify({"error": str(e), "field": e.field, "existing_upload_id": e.existing_upload_id}), 409

    return jsonify({
        "message": "Upload successful",
        "upload_id": upload_entity.upload_id,
        "uuid": upload_entity.uuid,
        "series": upload_entity.series,
        "lookup_path": upload_entity.lookup_path,
    }), 201


@cms_bp.route('/<series>/download/<int:upload_id>', methods=['GET'])
def download_by_id(series, upload_id):
    """Get upload by upload_id."""
    try:
        CMSUpload.validate_series(series)
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400

    upload = CMSUpload.get_by_upload_id(series, upload_id)
    if upload is None:
        return jsonify({"error": f"Upload {upload_id} not found in series '{series}'"}), 404

    return jsonify({"data": upload.to_dict()})


@cms_bp.route('/<series>/uuid/<uuid>', methods=['GET'])
def download_by_uuid(series, uuid):
    """Get upload by UUID."""
    try:
        CMSUpload.validate_series(series)
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400

    upload = CMSUpload.get_by_uuid(uuid)
    if upload is None:
        return jsonify({"error": f"Upload with UUID '{uuid}' not found"}), 404

    # Verify the upload belongs to the requested series
    if upload.series != series:
        return jsonify({"error": f"Upload with UUID '{uuid}' not found in series '{series}'"}), 404

    return jsonify({"data": upload.to_dict()})


@cms_bp.route('/<series>/path/<path:lookup_path>', methods=['GET'])
def download_by_path(series, lookup_path):
    """Get upload by lookup path."""
    try:
        CMSUpload.validate_series(series)
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400

    upload = CMSUpload.get_by_lookup_path(series, lookup_path)
    if upload is None:
        return jsonify({"error": f"Upload at path '{lookup_path}' not found in series '{series}'"}), 404

    return jsonify({"data": upload.to_dict()})


@cms_bp.route('/<series>/list', methods=['GET'])
def list_uploads(series):
    """List uploads in a series with cursor pagination."""
    try:
        CMSUpload.validate_series(series)
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400

    # Parse limit
    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        return jsonify({"error": "Invalid 'limit' parameter; must be an integer"}), 400

    if limit < 1:
        limit = 1
    elif limit > 200:
        limit = 200

    cursor = request.args.get('cursor', None)

    uploads, next_cursor = CMSUpload.list_by_series(series, limit=limit, cursor=cursor)

    return jsonify({
        "uploads": [u.to_dict_meta() for u in uploads],
        "series": series,
        "next_cursor": next_cursor.decode('utf-8') if isinstance(next_cursor, bytes) else next_cursor,
    })


@cms_bp.route('/<series>/delete/<int:upload_id>', methods=['DELETE'])
def delete_upload(series, upload_id):
    """Delete an upload (admin only)."""
    try:
        CMSUpload.validate_series(series)
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400

    # Admin-only check
    if not CMSConfig.is_admin(g.current_user.address):
        return jsonify({"error": "Admin access required"}), 403

    upload = CMSUpload.get_by_upload_id(series, upload_id)
    if upload is None:
        return jsonify({"error": f"Upload {upload_id} not found in series '{series}'"}), 404

    upload.delete_with_relationships()

    return jsonify({
        "message": "Upload deleted",
        "upload_id": upload_id,
        "series": series,
    })
