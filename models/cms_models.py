import base64
import re
import uuid as uuid_module

from google.cloud import ndb


class CMSValidationError(Exception):
    def __init__(self, message, field=None, value=None):
        super().__init__(message)
        self.field = field
        self.value = value


class CMSConflictError(Exception):
    def __init__(self, message, field=None, value=None, existing_upload_id=None):
        super().__init__(message)
        self.field = field
        self.value = value
        self.existing_upload_id = existing_upload_id


class CMSSeriesCounter(ndb.Model):
    """Per-series monotonic counter for upload ID allocation.

    Key: ndb.Key('CMSSeries', series, 'CMSSeriesCounter', 'counter')
    The counter is always incremented inside a transaction so that
    concurrent uploads never receive the same upload_id, and IDs are
    never reused even after deletion.
    """

    next_id = ndb.IntegerProperty(default=1)

    @classmethod
    def _key(cls, series):
        return ndb.Key('CMSSeries', series, cls, 'counter')

    @classmethod
    @ndb.transactional()
    def allocate_id(cls, series):
        """Atomically allocate the next upload_id for *series*."""
        key = cls._key(series)
        counter = key.get()
        if counter is None:
            counter = cls(key=key, next_id=1)
        allocated = counter.next_id
        counter.next_id = allocated + 1
        counter.put()
        return allocated


class CMSUpload(ndb.Model):
    """CMS Upload entity.

    Key hierarchy: parent = ndb.Key('CMSSeries', series), id = upload_id (int).
    """

    SERIES_PATTERN = r'^[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]$'
    LOOKUP_PATH_PATTERN = r'^(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.[A-Za-z0-9]+$'

    upload_id = ndb.IntegerProperty(required=True)
    uuid = ndb.StringProperty(required=True)
    series = ndb.StringProperty(required=True)
    lookup_path = ndb.StringProperty()
    content = ndb.BlobProperty()
    content_text = ndb.TextProperty()
    content_type = ndb.StringProperty(default="application/octet-stream")
    extra_metadata = ndb.JsonProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)
    source_ip = ndb.StringProperty()
    user_agent = ndb.TextProperty()
    signature = ndb.StringProperty()
    created_at = ndb.DateTimeProperty(auto_now_add=True)
    updated_at = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def _series_parent_key(cls, series):
        """Return the parent key for a given series."""
        return ndb.Key('CMSSeries', series)

    @classmethod
    def validate_series(cls, series):
        """Validate series name against pattern."""
        if not re.match(cls.SERIES_PATTERN, series):
            raise CMSValidationError(
                f"Invalid series name '{series}'. Must match pattern: {cls.SERIES_PATTERN}",
                field='series',
                value=series,
            )
        return True

    @classmethod
    def validate_lookup_path(cls, lookup_path):
        """Validate lookup_path against pattern."""
        if not re.match(cls.LOOKUP_PATH_PATTERN, lookup_path):
            raise CMSValidationError(
                f"Invalid lookup_path '{lookup_path}'. Must match pattern: {cls.LOOKUP_PATH_PATTERN}",
                field='lookup_path',
                value=lookup_path,
            )
        return True

    @classmethod
    def _get_next_upload_id(cls, series):
        """Allocate the next upload_id via a transactional per-series counter.

        IDs are strictly monotonic and never reused, even after deletion.
        """
        return CMSSeriesCounter.allocate_id(series)

    @classmethod
    def create_upload(cls, series, content_bytes=None, content_text=None,
                      content_type="application/octet-stream", extra_metadata=None,
                      lookup_path=None, source_ip=None, user_agent=None, signature=None):
        """Create a new upload in the given series."""
        # Validate series
        cls.validate_series(series)

        # Validate lookup_path if provided
        if lookup_path:
            cls.validate_lookup_path(lookup_path)
            # Check for conflict within the series
            existing = cls.get_by_lookup_path(series, lookup_path)
            if existing:
                raise CMSConflictError(
                    f"lookup_path '{lookup_path}' already exists in series '{series}'",
                    field='lookup_path',
                    value=lookup_path,
                    existing_upload_id=existing.upload_id,
                )

        # Handle UUID: extract from extra_metadata or auto-generate
        if extra_metadata and extra_metadata.get("uuid"):
            uuid_value = extra_metadata["uuid"]
            # Validate UUID format
            try:
                uuid_module.UUID(uuid_value)
            except (ValueError, AttributeError):
                raise CMSValidationError(
                    f"Invalid UUID format '{uuid_value}'",
                    field='uuid',
                    value=uuid_value,
                )
        else:
            uuid_value = str(uuid_module.uuid4())

        # Check UUID uniqueness globally
        existing_by_uuid = cls.get_by_uuid(uuid_value)
        if existing_by_uuid:
            raise CMSConflictError(
                f"UUID '{uuid_value}' already exists",
                field='uuid',
                value=uuid_value,
                existing_upload_id=existing_by_uuid.upload_id,
            )

        # Allocate next upload_id
        upload_id = cls._get_next_upload_id(series)
        parent_key = cls._series_parent_key(series)

        entity = cls(
            parent=parent_key,
            id=upload_id,
            upload_id=upload_id,
            uuid=uuid_value,
            series=series,
            lookup_path=lookup_path,
            content=content_bytes,
            content_text=content_text,
            content_type=content_type,
            extra_metadata=extra_metadata,
            source_ip=source_ip,
            user_agent=user_agent,
            signature=signature,
        )
        entity.put()
        return entity

    @classmethod
    def get_by_upload_id(cls, series, upload_id):
        """Get upload by direct key lookup."""
        return ndb.Key('CMSSeries', series, cls, upload_id).get()

    @classmethod
    def get_by_uuid(cls, uuid_value):
        """Get upload by UUID (global query across all series)."""
        return cls.query(cls.uuid == uuid_value).get()

    @classmethod
    def get_by_lookup_path(cls, series, lookup_path):
        """Get upload by lookup_path within a series (ancestor query)."""
        parent_key = cls._series_parent_key(series)
        return cls.query(
            cls.lookup_path == lookup_path,
            ancestor=parent_key
        ).get()

    @classmethod
    def list_by_series(cls, series, limit=20, cursor=None):
        """List uploads in a series with cursor-based pagination."""
        parent_key = cls._series_parent_key(series)
        query = cls.query(ancestor=parent_key).order(-cls.upload_id)

        if cursor:
            cursor = ndb.Cursor(urlsafe=cursor)

        results, next_cursor, more = query.fetch_page(limit, start_cursor=cursor)
        return results, (next_cursor.urlsafe() if next_cursor and more else None)

    def to_dict_meta(self):
        """Convert entity to a metadata-only dictionary (no content payload).

        Use this for list endpoints to avoid serializing potentially large
        binary / text payloads.
        """
        return {
            'upload_id': self.upload_id,
            'uuid': self.uuid,
            'series': self.series,
            'lookup_path': self.lookup_path,
            'content_type': self.content_type,
            'extra_metadata': self.extra_metadata,
            'source_ip': self.source_ip,
            'user_agent': self.user_agent,
            'signature': self.signature,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def to_dict(self):
        """Convert entity to dictionary including content."""
        result = self.to_dict_meta()

        # Content: base64 for binary, raw for text
        if self.content is not None:
            result['content'] = base64.b64encode(self.content).decode('utf-8')
        elif self.content_text is not None:
            result['content'] = self.content_text
        else:
            result['content'] = None

        return result

    def delete_with_relationships(self):
        """Delete this upload and cascade-delete all descendant relationships.

        This prevents orphaned CMSRelationship entities from being
        inherited by a future upload that might (in theory) receive the
        same entity key.
        """
        from models.graph_models import CMSRelationship

        # Fetch all relationship keys under this upload (active + removed)
        rel_keys = CMSRelationship.query(ancestor=self.key).fetch(keys_only=True)
        if rel_keys:
            ndb.delete_multi(rel_keys)
        self.key.delete()
