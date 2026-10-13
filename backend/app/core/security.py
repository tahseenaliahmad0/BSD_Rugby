"""Password hashing (Argon2id) and opaque session / CSRF tokens."""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    """A 256-bit random token, URL safe. Used for session cookies and CSRF cookies."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Sessions store only the hash so a database leak does not leak live sessions."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
