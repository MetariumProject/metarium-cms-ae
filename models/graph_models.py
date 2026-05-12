from google.cloud import ndb

from .cms_models import CMSValidationError


ALLOWED_PREDICATES = {
    "owl": ["owl:differentFrom", "owl:equivalentTo", "owl:sameAs"],
    "rdfs": ["rdfs:isDefinedBy", "rdfs:seeAlso", "rdfs:subClassOf"],
    "skos": [
        "skos:broadMatch", "skos:broader", "skos:closeMatch", "skos:exactMatch",
        "skos:narrowMatch", "skos:narrower", "skos:related", "skos:relatedMatch",
    ],
    "cause": [
        "cause:directCause", "cause:enables", "cause:indirectCause",
        "cause:prerequisite", "cause:prevents", "cause:trigger",
    ],
    "intent": [
        "intent:achieves", "intent:aimsTo", "intent:facilitates",
        "intent:intendedFor", "intent:motivates",
    ],
    "axiom": [
        "axiom:contradicts", "axiom:derivedFrom", "axiom:implies",
        "axiom:mutuallyExclusive", "axiom:necessaryFor", "axiom:sufficientFor",
    ],
    "spatial": [
        "spatial:connects", "spatial:contains", "spatial:locatedIn",
        "spatial:near", "spatial:within",
    ],
    "temporal": [
        "temporal:after", "temporal:before", "temporal:during",
        "temporal:hasVersion", "temporal:overlaps", "temporal:versionOf",
    ],
    "part": ["part:hasComponent", "part:hasPart", "part:isPartOf", "part:partOf"],
    "rel": [
        "rel:archivedFrom", "rel:creates", "rel:dependsOn", "rel:derivedFrom",
        "rel:hasPart", "rel:influences", "rel:interactsWith", "rel:linkedFrom",
        "rel:linksTo", "rel:modifies", "rel:partOf", "rel:referencedBy",
        "rel:references", "rel:relatedTo", "rel:sourceOf", "rel:usedDevice",
    ],
}

# Flat set for O(1) validation
ALL_PREDICATES = set()
for predicates in ALLOWED_PREDICATES.values():
    ALL_PREDICATES.update(predicates)


def validate_predicate(predicate: str) -> bool:
    return predicate in ALL_PREDICATES


class CMSRelationship(ndb.Model):
    """CMS Relationship entity, child of source CMSUpload entity.

    Key hierarchy: parent = ndb.Key('CMSSeries', series, 'CMSUpload', upload_id)
    """

    source_uuid = ndb.StringProperty(required=True)
    predicate = ndb.StringProperty(required=True)
    target_uuid = ndb.StringProperty(required=True)
    target_series = ndb.StringProperty()
    target_content_type = ndb.StringProperty()
    target_lookup_path = ndb.StringProperty()
    status = ndb.StringProperty(default='active', choices=['active', 'removed'])
    created_by = ndb.StringProperty()
    created_at = ndb.DateTimeProperty(auto_now_add=True)
    last_updated = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def create_relationship(cls, source_upload, predicate, target_upload, created_by):
        """Create a new relationship between two uploads."""
        if not validate_predicate(predicate):
            raise CMSValidationError(
                f"Invalid predicate '{predicate}'",
                field='predicate',
                value=predicate,
            )

        rel = cls(
            parent=source_upload.key,
            source_uuid=source_upload.uuid,
            predicate=predicate,
            target_uuid=target_upload.uuid,
            target_series=target_upload.series,
            target_content_type=target_upload.content_type,
            target_lookup_path=target_upload.lookup_path,
            status='active',
            created_by=created_by,
        )
        rel.put()
        return rel

    @classmethod
    def list_by_source(cls, source_upload, status='active'):
        """List relationships from a source upload, filtered by status."""
        return cls.query(
            cls.status == status,
            ancestor=source_upload.key
        ).order(-cls.created_at).fetch()

    @classmethod
    def get_by_id_and_parent(cls, relationship_id, source_upload):
        """Get a relationship by its ID and parent upload."""
        return ndb.Key(
            'CMSSeries', source_upload.series,
            'CMSUpload', source_upload.upload_id,
            cls, relationship_id
        ).get()

    def remove(self):
        """Soft-delete this relationship."""
        self.status = 'removed'
        self.put()

    def to_dict(self):
        """Convert entity to dictionary."""
        return {
            'relationship_id': self.key.id(),
            'source_uuid': self.source_uuid,
            'predicate': self.predicate,
            'target_uuid': self.target_uuid,
            'target_series': self.target_series,
            'target_content_type': self.target_content_type,
            'target_lookup_path': self.target_lookup_path,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }
