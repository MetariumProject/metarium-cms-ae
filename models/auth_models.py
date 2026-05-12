import json
import os
import time

import blake3
from google.cloud import ndb


class User(ndb.Model):
    """User entity keyed by SS58 address."""

    address = ndb.StringProperty(required=True)
    access_token = ndb.StringProperty()
    access_token_expires = ndb.FloatProperty()
    refresh_token = ndb.StringProperty()
    refresh_token_expires = ndb.FloatProperty()
    created_at = ndb.DateTimeProperty(auto_now_add=True)
    updated_at = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def get_by_address(cls, address):
        return cls.get_by_id(address)

    @classmethod
    def get_by_token(cls, token):
        return cls.query(
            cls.access_token == token,
            cls.access_token_expires > time.time()
        ).get()

    @classmethod
    def get_by_refresh_token(cls, refresh_token):
        return cls.query(
            cls.refresh_token == refresh_token,
            cls.refresh_token_expires > time.time()
        ).get()

    def generate_tokens(self):
        """Generate blake3-hashed random access token (1hr) + refresh token (30 days)."""
        raw_access = os.urandom(32)
        raw_refresh = os.urandom(32)

        self.access_token = blake3.blake3(raw_access).hexdigest()
        self.access_token_expires = time.time() + 3600  # 1 hour

        self.refresh_token = blake3.blake3(raw_refresh).hexdigest()
        self.refresh_token_expires = time.time() + (30 * 24 * 3600)  # 30 days

        self.put()

        return {
            "access_token": self.access_token,
            "access_token_expires": self.access_token_expires,
            "refresh_token": self.refresh_token,
            "refresh_token_expires": self.refresh_token_expires,
        }

    def invalidate_tokens(self):
        """Clear all token fields."""
        self.access_token = None
        self.access_token_expires = None
        self.refresh_token = None
        self.refresh_token_expires = None
        self.put()

    @classmethod
    def create_or_update(cls, address):
        user = cls.get_by_id(address)
        if not user:
            user = cls(id=address, address=address)
            user.put()
        return user


class Challenge(ndb.Model):
    """Challenge entity keyed by SS58 address, 5-minute expiry."""

    address = ndb.StringProperty(required=True)
    challenge_data = ndb.JsonProperty(required=True)
    challenge_json = ndb.TextProperty()  # canonical JSON for exact matching
    expires_at = ndb.FloatProperty(required=True)
    created_at = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def store_challenge(cls, address, challenge):
        # Delete any existing challenge for this address
        existing = cls.get_by_id(address)
        if existing:
            existing.key.delete()

        entity = cls(
            id=address,
            address=address,
            challenge_data=challenge,
            challenge_json=json.dumps(challenge, separators=(',', ':')),
            expires_at=time.time() + 300,  # 5 minutes
        )
        entity.put()
        return entity

    @classmethod
    def get_challenge(cls, address):
        challenge = cls.get_by_id(address)
        if challenge is None:
            return None
        if time.time() > challenge.expires_at:
            challenge.key.delete()
            return None
        return challenge

    @classmethod
    def clear_challenge(cls, address):
        challenge = cls.get_by_id(address)
        if challenge:
            challenge.key.delete()
