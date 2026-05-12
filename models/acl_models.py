from google.cloud import ndb


class CMSConfig(ndb.Model):
    """Singleton configuration entity keyed by id='config'."""

    admin_address = ndb.StringProperty(required=True)
    created_at = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def get_config(cls):
        return cls.get_by_id('config')

    @classmethod
    def set_admin(cls, address):
        config = cls.get_by_id('config')
        if config:
            config.admin_address = address
            config.put()
        else:
            config = cls(id='config', admin_address=address)
            config.put()
        return config

    @classmethod
    def is_admin(cls, address):
        config = cls.get_config()
        return config is not None and config.admin_address == address


class Scribe(ndb.Model):
    """Scribe entity keyed by SS58 address."""

    address = ndb.StringProperty(required=True)
    granted_by = ndb.StringProperty(required=True)
    created_at = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def get_by_address(cls, address):
        return cls.get_by_id(address)

    @classmethod
    def create(cls, address, granted_by):
        scribe = cls(id=address, address=address, granted_by=granted_by)
        scribe.put()
        return scribe

    @classmethod
    def delete_scribe(cls, address):
        scribe = cls.get_by_id(address)
        if scribe:
            scribe.key.delete()
            return True
        return False

    @classmethod
    def list_all(cls):
        return cls.query().fetch()

    @classmethod
    def is_scribe(cls, address):
        return cls.get_by_id(address) is not None
