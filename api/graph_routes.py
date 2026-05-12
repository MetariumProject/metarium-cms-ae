import logging

from flask import Blueprint, g, jsonify, request

from models.cms_models import CMSUpload, CMSValidationError
from models.graph_models import (
    ALLOWED_PREDICATES,
    CMSRelationship,
    validate_predicate,
)

logger = logging.getLogger(__name__)

graph_bp = Blueprint('graph', __name__)


# ---------------------------------------------------------------------------
# Helper: validate series and load source upload by upload_id
# ---------------------------------------------------------------------------

def _validate_series(series):
    """Validate series name. Returns (None, None) on success or (response, status) on error."""
    try:
        CMSUpload.validate_series(series)
    except CMSValidationError as e:
        return jsonify({"error": str(e), "field": e.field}), 400
    return None, None


def _load_source(series, upload_id):
    """Load source upload by series + upload_id. Returns (source, None) or (None, (response, status))."""
    source = CMSUpload.get_by_upload_id(series, upload_id)
    if source is None:
        return None, (jsonify({"error": "Upload not found"}), 404)
    return source, None


# ---------------------------------------------------------------------------
# POST /<series>/<int:upload_id>/graph/add
# ---------------------------------------------------------------------------

@graph_bp.route('/<series>/<int:upload_id>/graph/add', methods=['POST'])
def graph_add(series, upload_id):
    """Create a relationship from a source upload to a target upload."""
    err, status = _validate_series(series)
    if err is not None:
        return err, status

    source, err_tuple = _load_source(series, upload_id)
    if source is None:
        return err_tuple

    data = request.get_json(silent=True) or {}
    predicate = data.get('predicate')
    target_uuid = data.get('target_uuid')

    if not predicate or not target_uuid:
        return jsonify({"error": "predicate and target_uuid are required"}), 400

    # Validate predicate
    if not validate_predicate(predicate):
        return jsonify({
            "error": "Invalid predicate",
            "allowed_predicates": ALLOWED_PREDICATES,
        }), 400

    # Look up target
    target = CMSUpload.get_by_uuid(target_uuid)
    if target is None:
        return jsonify({"error": "Target UUID not found in CMS"}), 404

    # Prevent self-link
    if source.uuid == target_uuid:
        return jsonify({"error": "Cannot create relationship to self"}), 400

    # Create relationship
    rel = CMSRelationship.create_relationship(
        source_upload=source,
        predicate=predicate,
        target_upload=target,
        created_by=g.current_user.address,
    )

    return jsonify({
        "message": "Relationship created",
        "relationship": rel.to_dict(),
    }), 201


# ---------------------------------------------------------------------------
# GET /<series>/<int:upload_id>/graph/list
# ---------------------------------------------------------------------------

@graph_bp.route('/<series>/<int:upload_id>/graph/list', methods=['GET'])
def graph_list(series, upload_id):
    """List active relationships from a source upload."""
    err, status = _validate_series(series)
    if err is not None:
        return err, status

    source, err_tuple = _load_source(series, upload_id)
    if source is None:
        return err_tuple

    relationships = CMSRelationship.list_by_source(source, status='active')

    return jsonify({
        "relationships": [r.to_dict() for r in relationships],
        "upload_id": upload_id,
        "uuid": source.uuid,
    })


# ---------------------------------------------------------------------------
# POST /<series>/<int:upload_id>/graph/remove
# ---------------------------------------------------------------------------

@graph_bp.route('/<series>/<int:upload_id>/graph/remove', methods=['POST'])
def graph_remove(series, upload_id):
    """Soft-delete a relationship from a source upload."""
    err, status = _validate_series(series)
    if err is not None:
        return err, status

    source, err_tuple = _load_source(series, upload_id)
    if source is None:
        return err_tuple

    data = request.get_json(silent=True) or {}
    relationship_id = data.get('relationship_id')

    if relationship_id is None:
        return jsonify({"error": "relationship_id is required"}), 400

    rel = CMSRelationship.get_by_id_and_parent(relationship_id, source)
    if rel is None:
        return jsonify({"error": "Relationship not found"}), 404

    if rel.status == 'removed':
        return jsonify({"error": "Relationship already removed"}), 400

    rel.remove()

    return jsonify({
        "message": "Relationship removed",
        "relationship": rel.to_dict(),
    })


# ---------------------------------------------------------------------------
# GET /<series>/<int:upload_id>/graph/removed
# ---------------------------------------------------------------------------

@graph_bp.route('/<series>/<int:upload_id>/graph/removed', methods=['GET'])
def graph_removed(series, upload_id):
    """List removed relationships from a source upload."""
    err, status = _validate_series(series)
    if err is not None:
        return err, status

    source, err_tuple = _load_source(series, upload_id)
    if source is None:
        return err_tuple

    relationships = CMSRelationship.list_by_source(source, status='removed')

    return jsonify({
        "relationships": [r.to_dict() for r in relationships],
        "upload_id": upload_id,
        "uuid": source.uuid,
    })


# ---------------------------------------------------------------------------
# GET /<series>/graph/uuid/<uuid>
# ---------------------------------------------------------------------------

@graph_bp.route('/<series>/graph/uuid/<uuid>', methods=['GET'])
def graph_by_uuid(series, uuid):
    """List active relationships for an upload looked up by UUID."""
    err, status = _validate_series(series)
    if err is not None:
        return err, status

    source = CMSUpload.get_by_uuid(uuid)
    if source is None:
        return jsonify({"error": "Upload not found"}), 404

    if source.series != series:
        return jsonify({"error": "Upload not found"}), 404

    relationships = CMSRelationship.list_by_source(source, status='active')

    return jsonify({
        "relationships": [r.to_dict() for r in relationships],
        "upload_id": source.upload_id,
        "uuid": source.uuid,
    })


# ---------------------------------------------------------------------------
# GET /<series>/graph/uuid/<uuid>/removed
# ---------------------------------------------------------------------------

@graph_bp.route('/<series>/graph/uuid/<uuid>/removed', methods=['GET'])
def graph_by_uuid_removed(series, uuid):
    """List removed relationships for an upload looked up by UUID."""
    err, status = _validate_series(series)
    if err is not None:
        return err, status

    source = CMSUpload.get_by_uuid(uuid)
    if source is None:
        return jsonify({"error": "Upload not found"}), 404

    if source.series != series:
        return jsonify({"error": "Upload not found"}), 404

    relationships = CMSRelationship.list_by_source(source, status='removed')

    return jsonify({
        "relationships": [r.to_dict() for r in relationships],
        "upload_id": source.upload_id,
        "uuid": source.uuid,
    })


# ---------------------------------------------------------------------------
# GET /<series>/<int:upload_id>/graph/predicates
# ---------------------------------------------------------------------------

@graph_bp.route('/<series>/<int:upload_id>/graph/predicates', methods=['GET'])
def graph_predicates(series, upload_id):
    """Return the list of allowed predicates."""
    return jsonify({"predicates": ALLOWED_PREDICATES})
