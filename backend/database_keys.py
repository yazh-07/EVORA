"""Password-wrapped database keys; no plaintext master key or password on disk."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
from uuid import uuid4

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


def private(path):
    if os.name == 'nt':
        from backend.windows_credentials import secure_path
        secure_path(path)
    else:
        os.chmod(path, 0o600)


def sync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        private(temporary)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            fd = None
            json.dump(value, out, separators=(',', ':'))
            out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        temporary.unlink(missing_ok=True)


def user_key(username):
    return hashlib.sha256(username.casefold().encode()).hexdigest()


def derive(password, salt):
    return hash_secret_raw(password.encode(), salt, time_cost=3, memory_cost=65536,
                           parallelism=1, hash_len=32, type=Type.ID)


def encode(value):
    return base64.b64encode(value).decode('ascii')


def decode(value):
    return base64.b64decode(value, validate=True)


def wrap(key, password, aad):
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    encrypted = AESGCM(derive(password, salt)).encrypt(nonce, key, aad)
    return dict(salt=encode(salt), nonce=encode(nonce), ciphertext=encode(encrypted))


def unwrap(slot, password, aad):
    salt, nonce, ciphertext = (decode(slot[k]) for k in ('salt', 'nonce', 'ciphertext'))
    if len(salt) != 16 or len(nonce) != 12 or len(ciphertext) != 48:
        raise ValueError('Invalid wrapped key')
    return AESGCM(derive(password, salt)).decrypt(nonce, ciphertext, aad)


class KeyStore:
    def __init__(self, path):
        self.path = path

    def read(self):
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('users'), dict) or not isinstance(value.get('id'), str):
            raise ValueError('Invalid database key metadata')
        return value

    @staticmethod
    def aad(value, username, purpose):
        return f"evora-database/1:{value['id']}:{user_key(username)}:{purpose}".encode()

    def create(self, key, username, password, recovery):
        value = dict(version=1, id=str(uuid4()), users={})
        value['users'][user_key(username)] = {
            purpose: [wrap(key, secret, self.aad(value, username, purpose))]
            for purpose, secret in [('password', password), ('recovery', recovery)] if secret}
        atomic_json(self.path, value)

    def candidates(self, username, secret, purpose):
        value = self.read()
        slots = value['users'].get(user_key(username), {}).get(purpose, [])
        # A missing account still performs the same memory-hard work.
        if not slots:
            derive(secret, b'evora-unknown-id!')
        for slot in slots:
            try:
                yield unwrap(slot, secret, self.aad(value, username, purpose))
            except (ValueError, KeyError, TypeError, InvalidTag):
                continue

    def stage(self, key, username, password=None, recovery=None):
        """Write new wraps before the SQL transaction commits; retain old wraps on failure.

        On restart both can decrypt a candidate key, but only the credential matching
        the authoritative encrypted account row may actually unlock the database.
        """
        value = self.read()
        user = value['users'].setdefault(user_key(username), {})
        final = {}
        for purpose, secret in [('password', password), ('recovery', recovery)]:
            if secret is None:
                continue
            slot = wrap(key, secret, self.aad(value, username, purpose))
            # Preserve prior slots across repeated interruptions until SQL commits.
            user[purpose] = [slot] + user.get(purpose, [])
            final[purpose] = [slot]
        atomic_json(self.path, value)
        return final

    def finish(self, username, final):
        value = self.read()
        value['users'].setdefault(user_key(username), {}).update(final)
        atomic_json(self.path, value)
